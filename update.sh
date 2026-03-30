#!/bin/bash
# Newsfeed update script — called by cron
# Cron entry: 0 0,6,12,18 * * * /Users/cci-research/workspace/newsfeed/update.sh

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGFILE="$DIR/logs/update.log"
PYTHON="/Users/cci-research/miniconda3/bin/python3"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/cci-research/miniconda3/bin:$PATH"

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
PYTHONUNBUFFERED=1 "$PYTHON" scripts/run_all.py 2>&1 | tee -a "$LOGFILE"

# Force-push docs/ as an orphan commit to gh-pages (no history accumulation)
REPO_URL=$(git remote get-url origin)
TMPDIR=$(mktemp -d)

cp -r "$DIR/docs/." "$TMPDIR/"

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
