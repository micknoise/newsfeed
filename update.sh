#!/bin/bash
# Newsfeed hourly update script — called by cron
# Cron entry: 0 * * * * /Users/cci-research/workspace/newsfeed/update.sh

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGFILE="$DIR/logs/update.log"
PYTHON="/Users/cci-research/miniconda3/bin/python3"
KOKORO="/Users/cci-research/miniconda3/bin/kokoro"

# Ensure cron has the right PATH (includes ffmpeg, kokoro, git)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/cci-research/miniconda3/bin:$PATH"
export KOKORO_CMD="$KOKORO"

cd "$DIR"

# Load secrets from .env (WEB_SEARCH_API_KEY etc.)
if [ -f "$DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$DIR/.env"
  set +a
fi

echo "──────────────────────────────────────" >> "$LOGFILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') Starting update" >> "$LOGFILE"

# Run pipeline
"$PYTHON" scripts/run_all.py 2>&1 | tee -a "$LOGFILE"

# Commit and push if docs/ changed
if git diff --quiet docs/; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') No site changes to commit" >> "$LOGFILE"
else
  git add docs/
  git commit -m "Update: $(date '+%Y-%m-%d %H:%M')"
  git push
  echo "$(date '+%Y-%m-%d %H:%M:%S') Pushed to GitHub" >> "$LOGFILE"
fi
