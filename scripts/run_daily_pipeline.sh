#!/usr/bin/env bash
set -euo pipefail

WEB_DIR="${HNDAILY_WEB_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SKILL_DIR="${HNDAILY_SKILL_DIR:-/Users/skr/Work/hndaily/hndaily-skill}"
DATE_ARG="${HNDAILY_DATE:-}"

mkdir -p "$WEB_DIR/data/raw" "$WEB_DIR/data/intermediate" "$WEB_DIR/data/tmp"

if [ -n "$DATE_ARG" ]; then
  RAW_JSON="$(python3 "$SKILL_DIR/crawler.py" "$DATE_ARG")"
else
  RAW_JSON="$(python3 "$SKILL_DIR/crawler.py")"
fi

echo "Raw crawler JSON: $RAW_JSON"
echo "Next step: generate content/daily/<date>.json from raw data, validate it, then render site/."
echo "Raw and intermediate files stay ignored by git."
