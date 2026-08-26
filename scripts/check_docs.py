"""
Guard against documentation drift.

CLAUDE.md deliberately does not enumerate the settings in config.yaml — an
enumeration kept in two places is exactly what goes stale. Instead config.yaml
is the single source of truth, which only works if every setting there actually
explains itself. This checks that.

A setting passes if it has a `#` comment on the line above it (or on the same
line), or if it is listed in SELF_EVIDENT below.

Run directly, or via update.sh, which reports failures without ever aborting
the pipeline.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONFIG = ROOT / "config.yaml"

# Settings whose names say everything worth saying.
SELF_EVIDENT = {
    "site_title",
    "timezone",
    "retention_days",
    "audio_enabled",
    "tts_voice",
    "audio_speed",
}


def _settings_block(lines: list[str]) -> tuple[int, int]:
    """Line range of the top-level `settings:` mapping."""
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^settings:\s*$", line):
            start = i + 1
            break
    if start is None:
        raise SystemExit("check_docs: no top-level `settings:` block in config.yaml")

    for j in range(start, len(lines)):
        # A non-indented, non-blank, non-comment line ends the block.
        if lines[j].strip() and not lines[j].startswith((" ", "\t", "#")):
            return start, j
    return start, len(lines)


def undocumented() -> list[str]:
    lines = CONFIG.read_text().splitlines()
    start, end = _settings_block(lines)

    missing = []
    for i in range(start, end):
        m = re.match(r"^\s{2}([A-Za-z_][\w]*):\s*(.*)$", lines[i])
        if not m:
            continue
        key, rest = m.group(1), m.group(2)
        if key in SELF_EVIDENT:
            continue
        # Comment on the same line, or on any unbroken run of comment lines above.
        if "#" in rest:
            continue
        k = i - 1
        while k >= start and lines[k].strip().startswith("#"):
            break
        else:
            missing.append(key)
            continue
        if not lines[k].strip().startswith("#"):
            missing.append(key)
    return missing


def main() -> int:
    missing = undocumented()
    if missing:
        print("[check_docs] settings in config.yaml with no explanatory comment:")
        for k in missing:
            print(f"  - {k}")
        print("[check_docs] add a comment above each, or list it in SELF_EVIDENT "
              "in scripts/check_docs.py if the name genuinely says it all.")
        return 1
    print("[check_docs] all config.yaml settings are documented")
    return 0


if __name__ == "__main__":
    sys.exit(main())
