"""
Generate per-article OGG audio files using the local kokoro CLI.
Audio is stored at docs/audio/items/<item_id>.ogg and served statically.
After each run, all current item OGGs are concatenated into
docs/audio/latest.ogg for a single downloadable listen.
Old audio files for expired items are deleted to keep the repo lean.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import yaml
from src import db
from src.text import strip_markdown

AUDIO_DIR = ROOT / "docs" / "audio" / "items"
KOKORO    = "/Users/cci-research/miniconda3/bin/kokoro"
FFMPEG    = "/opt/homebrew/bin/ffmpeg"


def _load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def generate_item_audio(item_id: int, text: str, voice: str, speed: float) -> bool:
    """Generate OGG for a single item. Returns True on success."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    ogg_path = AUDIO_DIR / f"{item_id}.ogg"

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix="nf_") as f:
            wav_path = f.name

        r = subprocess.run(
            [KOKORO, "-t", text, "-m", voice, "-s", str(speed), "-o", wav_path],
            capture_output=True, timeout=60,
        )
        if r.returncode != 0:
            print(f"[audio] kokoro failed for item {item_id}: {r.stderr.decode()[:100]}")
            return False

        r = subprocess.run(
            [FFMPEG, "-y", "-i", wav_path,
             "-c:a", "libvorbis", "-q:a", "4", str(ogg_path)],
            capture_output=True, timeout=30,
        )
        Path(wav_path).unlink(missing_ok=True)

        if r.returncode != 0:
            print(f"[audio] ffmpeg failed for item {item_id}")
            return False

        return True
    except Exception as e:
        print(f"[audio] Error for item {item_id}: {e}")
        return False


def build_latest_concat() -> bool:
    """Concatenate all current item OGGs (ordered by published_at desc) into
    docs/audio/latest.ogg for download. Returns True on success."""
    if not AUDIO_DIR.exists():
        return False

    # Get all items that have audio, ordered newest-first
    with db._connect() as conn:
        rows = conn.execute(
            """SELECT id FROM items
               WHERE audio_done = 1
               ORDER BY COALESCE(published_at, fetched_at) DESC"""
        ).fetchall()

    ogg_files = []
    for row in rows:
        p = AUDIO_DIR / f"{row[0]}.ogg"
        if p.exists():
            ogg_files.append(p)

    if not ogg_files:
        return False

    latest_path = ROOT / "docs" / "audio" / "latest.ogg"

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="nf_concat_"
        ) as f:
            for p in ogg_files:
                f.write(f"file '{p.resolve()}'\n")
            list_path = f.name

        r = subprocess.run(
            [FFMPEG, "-y", "-f", "concat", "-safe", "0",
             "-i", list_path, "-c", "copy", str(latest_path)],
            capture_output=True, timeout=120,
        )
        Path(list_path).unlink(missing_ok=True)

        if r.returncode != 0:
            print(f"[audio] concat failed: {r.stderr.decode()[:200]}")
            return False

        print(f"[audio] latest.ogg built from {len(ogg_files)} files")
        return True
    except Exception as e:
        print(f"[audio] concat error: {e}")
        return False


def cleanup_orphaned_audio() -> int:
    """Delete OGG files for items no longer in the DB."""
    if not AUDIO_DIR.exists():
        return 0

    with db._connect() as conn:
        live_ids = {
            str(r[0])
            for r in conn.execute("SELECT id FROM items").fetchall()
        }

    removed = 0
    for ogg in AUDIO_DIR.glob("*.ogg"):
        if ogg.stem not in live_ids:
            ogg.unlink()
            removed += 1

    return removed


def run() -> int:
    config = _load_config()
    db.init_db()

    voice = config["settings"].get("tts_voice", "af_sky")
    speed = config["settings"].get("audio_speed", 1.0)

    items = db.get_items_needing_audio(limit=80)
    if not items:
        print("[audio] No new audio to generate")
    else:
        print(f"[audio] Generating audio for {len(items)} items...")

    generated = 0
    for row in items:
        text = strip_markdown(f"{row['title']}. {row['summary'] or ''}")
        if not text:
            db.mark_audio_done(row["id"])
            continue

        ok = generate_item_audio(row["id"], text, voice, speed)
        if ok:
            db.mark_audio_done(row["id"])
            generated += 1
            print(f"[audio]   ✓ item {row['id']}: {row['title'][:50]}")
        else:
            print(f"[audio]   ✗ item {row['id']}: {row['title'][:50]}")

    removed = cleanup_orphaned_audio()
    if removed:
        print(f"[audio] Cleaned up {removed} expired audio files")

    build_latest_concat()

    return generated


if __name__ == "__main__":
    run()
