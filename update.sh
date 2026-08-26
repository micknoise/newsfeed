#!/bin/bash
# Newsfeed update script — called by cron
# Cron entry: 0 0,6,12,18 * * * /Users/cci-research/workspace/newsfeed/update.sh

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGFILE="$DIR/logs/update.log"
PYTHON="$DIR/.venv/bin/python3"

export PATH="$DIR/.venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

cd "$DIR"

# Load secrets
if [ -f "$DIR/.env" ]; then
  set -a
  source "$DIR/.env"
  set +a
fi

echo "──────────────────────────────────────" >> "$LOGFILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') Starting update" >> "$LOGFILE"

# Run pipeline (generates docs/ locally)
PYTHONUNBUFFERED=1 "$PYTHON" scripts/run_all.py 2>&1 | tee -a "$LOGFILE" || echo "$(date '+%Y-%m-%d %H:%M:%S') Pipeline exited non-zero, continuing to push existing docs/" >> "$LOGFILE"

# Warn on documentation drift. Never fatal — `set -e` is active and a stale
# comment must not stop the site from publishing.
"$PYTHON" scripts/check_docs.py >> "$LOGFILE" 2>&1 || \
  echo "$(date '+%Y-%m-%d %H:%M:%S') check_docs reported drift (see above)" >> "$LOGFILE"

# Force-push docs/ as an orphan commit to gh-pages (no history accumulation)
REPO_URL=$(git remote get-url origin)
TMPDIR=$(mktemp -d)

cp -r "$DIR/docs/." "$TMPDIR/"
# Finder leaves .DS_Store in docs/; git add -A below would publish it to the
# public branch every run. Target it by name — do NOT exclude dotfiles wholesale,
# because docs/.nojekyll must ship (without it Pages runs Jekyll over the site).
find "$TMPDIR" -name '.DS_Store' -delete

(
  cd "$TMPDIR"
  git init -b gh-pages .
  git config user.name  "$(git -C "$DIR" config user.name)"
  git config user.email "$(git -C "$DIR" config user.email)"
  git add -A
  git commit -m "Update: $(date '+%Y-%m-%d %H:%M')"
  git remote add origin "$REPO_URL"
  git push --force origin gh-pages
) >> "$LOGFILE" 2>&1

rm -rf "$TMPDIR"
echo "$(date '+%Y-%m-%d %H:%M:%S') Pushed to gh-pages" >> "$LOGFILE"
