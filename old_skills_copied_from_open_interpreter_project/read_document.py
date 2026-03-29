"""Extract text from a local file (PDF, TXT, VTT, SRT, etc.), suitable for speaking aloud."""

import re as _re
import sys
from pathlib import Path

_skills_dir = str(Path(__file__).parent)
if _skills_dir not in sys.path:
    sys.path.insert(0, _skills_dir)


def _parse_vtt_srt(text: str) -> str:
    """Strip timing markers and inline tags from VTT/SRT, returning clean transcript lines."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip headers and metadata
        if line in ("WEBVTT",) or line.startswith(("Kind:", "Language:", "NOTE", "STYLE", "REGION")):
            continue
        # Skip timing lines: 00:00:00.000 --> 00:00:00.000 ...
        if _re.match(r'^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->', line):
            continue
        # Skip SRT sequence numbers
        if _re.match(r'^\d+$', line):
            continue
        # Strip inline timing tags <00:00:00.000> and formatting tags <c>, </c>, <b>, etc.
        clean = _re.sub(r'<[^>]+>', '', line).strip()
        if clean:
            lines.append(clean)
    # Deduplicate consecutive identical lines (VTT repeats each line as it builds up)
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return '\n'.join(deduped)


def read_document(file_path: str, max_chars: int = 8000) -> str:
    """
    Extract readable text from a local file.

    Supports PDF, TXT, MD, VTT, SRT, and most plain-text formats.
    Suitable for passing directly to speak() to read a document aloud,
    or for summarisation. VTT/SRT subtitle files are cleaned of timing
    markers so only the spoken text is returned.

    Args:
        file_path: Path to the file to read.
        max_chars: Maximum characters to return (default 8000, ~10 min of speech).

    Returns:
        Extracted plain text.

    Examples:
        read_document("/tmp/report.pdf")
        read_document("/tmp/notes.txt")
        read_document("/tmp/captions.vtt")
    """
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        import pypdf
        reader = pypdf.PdfReader(str(path))
        pages  = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages.append(t.strip())
        text = "\n\n".join(pages)
        if not text.strip():
            raise ValueError("Could not extract text from PDF — it may be scanned/image-based.")
        return text[:max_chars]

    if suffix in (".vtt", ".srt", ".srv1", ".srv2", ".srv3"):
        raw = path.read_text(errors="replace")
        return _parse_vtt_srt(raw)[:max_chars]

    # Plain text fallback (txt, md, csv, etc.)
    return path.read_text(errors="replace")[:max_chars]


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test.pdf"
    print(read_document(path))
