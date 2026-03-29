"""Generate speech from text using Kokoro and send as audio via the active channel."""

import os
import re
import sys
import tempfile
from pathlib import Path

_skills_dir = str(Path(__file__).parent)
if _skills_dir not in sys.path:
    sys.path.insert(0, _skills_dir)

_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from kokoro import KPipeline
        _pipeline = KPipeline(lang_code="a")
    return _pipeline


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting so it doesn't get read aloud."""
    text = re.sub(r"```[\s\S]*?```", "", text)          # code blocks
    text = re.sub(r"`[^`]+`", "", text)                  # inline code
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)        # bold/italic
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)        # links
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE) # list bullets
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def speak(text: str, voice: str = "af_sky") -> str:
    """
    Generate speech from text using Kokoro TTS and send as an audio file.

    Uses the af_sky voice by default. Automatically sends via the active
    channel (Telegram or iMessage).

    Args:
        text:  The text to speak.
        voice: Kokoro voice name (default: "af_sky").

    Returns:
        Confirmation string.

    Examples:
        speak("Hello, the weather today is sunny.")
        speak("Your file has been downloaded.", voice="af_sky")
    """
    import numpy as np
    import soundfile as sf
    from send_file import send_file

    clean = _strip_markdown(text)
    if not clean:
        return "Nothing to speak."

    pipeline = _get_pipeline()
    chunks = []
    for _, _, audio in pipeline(clean, voice=voice, speed=1.0):
        if audio is not None:
            chunks.append(audio)

    if not chunks:
        return "No audio generated."

    audio_data = np.concatenate(chunks)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix="oi_speak_")
    sf.write(tmp.name, audio_data, 24000)
    tmp.close()

    try:
        result = send_file(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    return f"Spoken and sent ({len(clean)} chars)."


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "Hello, this is a test."
    print(speak(text))
