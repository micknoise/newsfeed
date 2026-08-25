# Newsfeed

A personal newsfeed aggregator that fetches RSS articles, summarises them with a local LLM (with a groundedness check against the source), classifies them into themes, and publishes a static site to GitHub Pages — updated 4× daily by cron.

> **Audio narration is currently disabled** (`settings.audio_enabled: false`). It was slow to render and rarely used. The code is retained — set the flag to `true` to bring it back, which re-enables the Kokoro/ffmpeg prerequisites below.

## Prerequisites

- **Python 3.12+** (via [miniconda](https://docs.conda.io/en/latest/miniconda.html) or system Python)
- **[LM Studio](https://lmstudio.ai/)** running a local model (e.g. Devstral 2) on `localhost:1234` with the OpenAI-compatible API enabled
- **[Kokoro TTS](https://github.com/remsky/Kokoro-FastAPI)** CLI at `/Users/cci-research/miniconda3/bin/kokoro` — *only if `audio_enabled: true`*
- **ffmpeg** (`brew install ffmpeg`) — *only if `audio_enabled: true`*
- **git** with a remote configured (GitHub repo)
- **Brave Search API key** — get one at [brave.com/search/api](https://brave.com/search/api/)

## Setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/newsfeed.git
cd newsfeed
pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp .env.example .env
```

Edit `.env` and add your Brave Search API key:

```
WEB_SEARCH_API_KEY=your_key_here
```

### 3. Configure feeds and settings

Edit `config.yaml` to adjust:
- RSS feeds under `feeds:`
- `retention_days` (default: 3)
- `items_per_feed` (default: 12)
- `audio_enabled` (default `false`), `tts_voice`, `audio_speed`
- `verify_summaries` — re-check each summary against the article and discard unsupported ones
- `min_source_chars` — minimum real article text before the LLM is asked to summarise at all
- `llm.model` to match your LM Studio model name

### 4. Start your local LLM

Open LM Studio, load your model, and start the local server on port 1234 with the OpenAI-compatible API enabled.

### 5. First run

```bash
python3 scripts/run_all.py
```

This will:
1. Fetch all RSS feeds
2. Summarise new articles with the LLM
3. Classify articles into themes
4. Generate the digest summary
5. Generate per-article TTS audio *(skipped while `audio_enabled: false`)*
6. Build the static site into `docs/`

The first run may take 10–20 minutes depending on your LLM speed and number of feeds.

## GitHub Pages deployment

### 1. Create the repository on GitHub

Push the `main` branch:

```bash
git remote add origin https://github.com/YOUR_USERNAME/newsfeed.git
git push -u origin main
```

### 2. Configure GitHub Pages

In your GitHub repo settings → Pages → set source to the `gh-pages` branch (root). The `gh-pages` branch is created automatically on the first `update.sh` run.

### 3. Set up automated updates with cron

```bash
crontab -e
```

Add:

```
0 0,6,12,18 * * * /Users/cci-research/workspace/newsfeed/update.sh >> /Users/cci-research/workspace/newsfeed/logs/cron.log 2>&1
```

The `update.sh` script runs the full pipeline and then force-pushes the built `docs/` as an orphan commit to the `gh-pages` branch, so build output never accumulates in git history.

### 4. Manual update

```bash
./update.sh
```

## Project structure

```
scripts/       Pipeline stages (fetch, classify, summarise, make_audio, build_site, run_all)
src/           Shared modules (db, llm, rss, web, search, text)
templates/     Jinja2 HTML templates
docs/          Built static site (gitignored on main; deployed via gh-pages)
config.yaml    Feeds and settings
update.sh      Cron entry point
```

## Running individual stages

```bash
python3 scripts/fetch.py       # Fetch RSS + summarise new items
python3 scripts/classify.py    # Classify unsummarised items into themes
python3 scripts/summarise.py   # Generate digest + summary.ogg
python3 scripts/make_audio.py  # Generate per-article audio (only if audio_enabled)
python3 scripts/build_site.py  # Build static HTML into docs/
```
