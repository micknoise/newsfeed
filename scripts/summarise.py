"""
Generate an overall digest from recent items and produce a pre-computed
OGG audio file using the local kokoro CLI + ffmpeg.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import yaml
from datetime import datetime, timedelta, timezone

from src import db, llm
from src.text import strip_markdown

AUDIO_DIR = ROOT / "docs" / "audio"
AUDIO_OUT = AUDIO_DIR / "summary.ogg"

_SYSTEM = """You are a news digest writer for a personal newsfeed.
Write a flowing, readable summary (4-6 paragraphs) of the most important
recent stories from the list provided. Group related topics together.
Write in clear, neutral prose suitable for reading aloud. Do not use
markdown headers or bullet points — just paragraphs."""


def _load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def generate_digest(items: list, max_tokens: int) -> str:
    if not items:
        return "No recent news available."

    lines = []
    for row in items[:60]:  # cap context
        lines.append(f"- [{row['feed_label']}] {row['title']}: {(row['summary'] or '')[:150]}")

    prompt = "Recent news items:\n\n" + "\n".join(lines)
    return llm.complete(prompt, system=_SYSTEM, max_tokens=max_tokens)


def generate_audio(text: str, voice: str = "af_sky", speed: float = 1.0) -> bool:
    """Generate OGG audio from text using kokoro CLI + ffmpeg.
    Returns True on success."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix="newsfeed_") as wav_f:
            wav_path = wav_f.name

        # kokoro CLI: read from stdin via -t flag
        result = subprocess.run(
            ["kokoro", "-t", text, "-m", voice, "-s", str(speed), "-o", wav_path],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"[summarise] kokoro error: {result.stderr[:200]}")
            return False

        # Convert WAV → OGG Vorbis
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", wav_path,
                "-c:a", "libvorbis", "-q:a", "4",
                str(AUDIO_OUT),
            ],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"[summarise] ffmpeg error: {result.stderr[:200]}")
            return False

        Path(wav_path).unlink(missing_ok=True)
        print(f"[summarise] Audio written to {AUDIO_OUT}")
        return True
    except Exception as e:
        print(f"[summarise] Audio generation failed: {e}")
        return False


def run() -> str:
    config = _load_config()
    db.init_db()

    retention = config["settings"]["retention_days"]
    max_tokens = config["llm"].get("max_tokens_digest", 800)
    voice = config["settings"].get("tts_voice", "af_sky")
    speed = config["settings"].get("audio_speed", 1.0)

    last = db.get_latest_digest()
    if last:
        since = datetime.fromisoformat(str(last["created_at"])).replace(tzinfo=timezone.utc)
    else:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
    items = db.get_items_since(since, days=retention)
    print(f"[summarise] Building digest from {len(items)} new items (since {since.strftime('%Y-%m-%d %H:%M UTC')})...")

    digest = generate_digest(items, max_tokens)
    db.save_digest(digest, len(items))
    print("[summarise] Digest saved")

    generate_audio(strip_markdown(digest), voice=voice, speed=speed)
    return digest


if __name__ == "__main__":
    run()
