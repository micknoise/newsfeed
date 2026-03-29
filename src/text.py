"""Text utilities."""

import re


def strip_markdown(text: str) -> str:
    """Remove markdown formatting so it doesn't get read aloud by TTS."""
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", "", text)           # fenced code blocks
    text = re.sub(r"`[^`]+`", "", text)                   # inline code
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headings
    text = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)     # bold/italic
    text = re.sub(r"_{1,3}([^_\n]+)_{1,3}", r"\1", text)       # underscore bold/italic
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)       # links → label only
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE) # list bullets
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE) # numbered lists
    text = re.sub(r"^[-_*]{3,}\s*$", "", text, flags=re.MULTILINE) # horizontal rules
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
