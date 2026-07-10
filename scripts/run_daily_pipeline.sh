#!/usr/bin/env bash
set -euo pipefail

WEB_DIR="${HNDAILY_WEB_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SKILL_DIR="${HNDAILY_SKILL_DIR:-/Users/skr/Work/hndaily/hndaily-skill}"
DATE_ARG="${HNDAILY_DATE:-}"
INTERMEDIATE_DIR="${HNDAILY_INTERMEDIATE_DIR:-$WEB_DIR/data/intermediate}"

mkdir -p "$WEB_DIR/data/raw" "$INTERMEDIATE_DIR" "$WEB_DIR/data/tmp"

if [ -z "${HNDAILY_RAW_JSON:-}" ]; then
  if [ -n "$DATE_ARG" ]; then
    RAW_JSON="$(python3 "$SKILL_DIR/crawler.py" "$DATE_ARG")"
  else
    RAW_JSON="$(python3 "$SKILL_DIR/crawler.py")"
  fi
else
  RAW_JSON="$HNDAILY_RAW_JSON"
fi

DATE_STEM="$(basename "$RAW_JSON" .json)"
MODEL_INPUT_JSON="$INTERMEDIATE_DIR/$DATE_STEM.model-input.json"
MODEL_OUTPUT_JSON="$INTERMEDIATE_DIR/$DATE_STEM.model-output.json"
PREFILTER_JSON="$INTERMEDIATE_DIR/$DATE_STEM.prefilter.json"
EDITORIAL_AUDIT_JSON="$INTERMEDIATE_DIR/$DATE_STEM.editorial-audit.json"

python3 "$WEB_DIR/scripts/prepare_model_input.py" "$RAW_JSON" "$MODEL_INPUT_JSON" "$PREFILTER_JSON" >/dev/null

echo "RAW_JSON=$RAW_JSON"
echo "MODEL_INPUT_JSON=$MODEL_INPUT_JSON"
echo "MODEL_OUTPUT_JSON=$MODEL_OUTPUT_JSON"
echo "PREFILTER_JSON=$PREFILTER_JSON"
echo "EDITORIAL_AUDIT_JSON=$EDITORIAL_AUDIT_JSON"
