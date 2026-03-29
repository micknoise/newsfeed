"""Analyse text from a URL, local file, or raw text for psychological manipulation techniques."""

import os
import sys
from pathlib import Path

_skills_dir = str(Path(__file__).parent)
if _skills_dir not in sys.path:
    sys.path.insert(0, _skills_dir)

# Lexicon location — repo root sibling, or OI skills install location
_REPO_ROOT = Path(__file__).parent.parent
_LEXICON_CANDIDATES = [
    _REPO_ROOT / "Lexicon_of_Psychological_Manipulations.txt",
    Path.home() / "Library/Application Support/open-interpreter/Lexicon_of_Psychological_Manipulations.txt",
]


def _load_lexicon() -> str:
    for candidate in _LEXICON_CANDIDATES:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "Lexicon_of_Psychological_Manipulations.txt not found. "
        "Expected at: " + str(_LEXICON_CANDIDATES[0])
    )


def _extract_text(source: str, max_chars: int = 12000) -> str:
    """
    Extract plain text from a URL, local file path, or return raw text as-is.

    Detection order:
      1. Starts with http:// or https:// → fetch as URL
      2. Path exists on disk → read as file (PDF, TXT, etc.)
      3. Otherwise → treat as raw text
    """
    source = source.strip()

    if source.startswith(("http://", "https://")):
        from read_url import read_url
        return read_url(source, max_chars=max_chars)

    p = Path(source).expanduser()
    if p.exists():
        from read_document import read_document
        return read_document(str(p), max_chars=max_chars)

    return source[:max_chars]


def analyse_manipulation(source: str, max_chars: int = 12000) -> str:
    """
    Analyse text from a URL, local file, or raw text for psychological manipulation techniques.

    Extracts text from the given source and uses the local devstral model (via LM Studio)
    to identify which techniques from the Lexicon of Psychological Manipulations may be present,
    citing specific passages as evidence.

    Args:
        source:    A URL (https://...), a local file path (/tmp/doc.pdf), or raw text to analyse.
        max_chars: Maximum characters to extract from the source (default 12000).

    Returns:
        A structured analysis report listing detected techniques, evidence, and an
        overall assessment of the content's manipulative intent and severity.

    Examples:
        analyse_manipulation("https://example.com/marketing-page")
        analyse_manipulation("/tmp/received_document.pdf")
        analyse_manipulation("Buy now — only 3 left! Everyone is switching to us.")
    """
    from openai import OpenAI

    api_base  = os.environ.get("OI_API_BASE", "http://localhost:1234/v1")
    api_key   = os.environ.get("OI_API_KEY",  "lm-studio")
    # OI_MODEL is e.g. "openai/mistralai/devstral-small-2-2512" — strip the "openai/" prefix
    raw_model = os.environ.get("OI_MODEL", "mistralai/devstral-small-2-2512")
    model     = raw_model.removeprefix("openai/")

    client = OpenAI(base_url=api_base, api_key=api_key)

    lexicon = _load_lexicon()

    try:
        content_text = _extract_text(source, max_chars=max_chars)
    except Exception as e:
        return f"Error extracting text from source: {e}"

    if not content_text or len(content_text.strip()) < 20:
        return "Could not extract meaningful text from the given source."

    system_prompt = f"""You are an expert analyst in social psychology, persuasion science, and media literacy.
You have been given a reference lexicon of psychological manipulation and compliance techniques.

Your task is to carefully read a piece of content and identify which manipulation techniques from the lexicon
are present, providing specific evidence from the text for each finding.

LEXICON OF PSYCHOLOGICAL MANIPULATION TECHNIQUES:
{lexicon}

OUTPUT FORMAT:
Return a structured report with the following sections:

## Summary
A 2-3 sentence overview of what the content is and your overall assessment of its manipulative intent.

## Detected Techniques
For each technique you identify, use this format:

### [Technique Number and Name]
**Evidence:** Direct quote or paraphrase from the text showing this technique in use.
**How it works:** Brief explanation of the mechanism being exploited.
**Severity:** Low / Medium / High

## Overall Assessment
- **Manipulative Intent:** (Low / Medium / High / Very High)
- **Primary Domain:** (e.g. Marketing, Scam, Institutional, Interpersonal)
- **Key concerns:** Bullet-point summary of the most important findings.
- **Recommendation:** What a reader should be aware of or do in response.

If no manipulation techniques are clearly present, say so plainly and explain why the content appears benign."""

    response = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"Please analyse the following content for psychological manipulation techniques:\n\n---\n{content_text}\n---"},
        ],
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "Buy now — only 3 left! Everyone loves this product. Don't miss out."
    print(analyse_manipulation(source))
