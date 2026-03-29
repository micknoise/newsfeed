# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A personal static newsfeed site deployed via GitHub Pages (`micknoise/newsfeed`). A local cron job runs `update.sh` every hour, which: fetches RSS feeds → LLM-summarises articles → LLM-classifies into themes → generates an overall digest → renders static HTML → generates OGG audio → commits and pushes to GitHub.

## Commands

```bash
# Run the full pipeline once (requires local LLM at localhost:1234/v1)
python3 scripts/run_all.py

# Run individual steps
python3 scripts/fetch.py       # RSS fetch + per-article LLM summaries
python3 scripts/classify.py    # LLM theme classification
python3 scripts/summarise.py   # Overall digest + OGG audio generation
python3 scripts/build_site.py  # Render Jinja2 templates → docs/

# Tail the cron log
tail -f logs/update.log
```

## Architecture

```
src/          Core library (no side effects, importable)
  db.py       SQLite helpers — all DB access goes through here
  llm.py      OpenAI-compat client for localhost:1234/v1 (Devstral 2)
  rss.py      feedparser wrapper, normalises entries to dicts
  web.py      trafilatura URL→text extractor with requests fallback
  search.py   Brave Search API (requires WEB_SEARCH_API_KEY in .env)

scripts/      Pipeline steps, each has a run() function
  fetch.py    RSS → DB, then LLM summaries for new items
  classify.py LLM assigns theme + tags to unclassified items
  summarise.py  Overall digest + kokoro CLI + ffmpeg → docs/audio/summary.ogg
  build_site.py Jinja2 → docs/index.html + docs/feed.html
  run_all.py  Orchestrator: calls each step in order

templates/    Jinja2 — base.html, index.html (themes), feed.html (chronological)
docs/         GitHub Pages output (committed to repo)
  style.css   Static — responsive CSS with dark mode
  script.js   Static — pre-computed audio player + @huggingface/transformers browser TTS
data/         SQLite DB — gitignored, stores last 3 days of items
```

## Key design decisions

- **DB is gitignored** — `data/newsfeed.db` is local only. The site is fully rebuilt from DB on each run.
- **`docs/audio/summary.ogg` is gitignored** — regenerated each hour and committed separately.
- **Themes are LLM-discovered** — no fixed categories. `classify.py` passes existing themes as context to encourage consistency.
- **Two TTS modes** — pre-computed OGG (kokoro CLI + ffmpeg) for the digest, and client-side `@huggingface/transformers` (Kokoro, downloads ~80 MB on first browser use) for ad-hoc reading of any text.
- **Fault-tolerant pipeline** — each step in `run_all.py` catches exceptions so a LLM failure doesn't break the site build.

## Config

`config.yaml` — feeds list, LLM model/URL, retention days, TTS voice.
`.env` — secrets (`WEB_SEARCH_API_KEY`). Copy from `.env.example`.

## Cron setup

```bash
crontab -e
# Add:
0 * * * * /Users/cci-research/workspace/newsfeed/update.sh
```

## LLM

Local Devstral 2 via LM Studio at `http://localhost:1234/v1`. All calls go through `src/llm.py`. Model name comes from `config.yaml` → `llm.model` but can be overridden via `LLM_MODEL` env var.
