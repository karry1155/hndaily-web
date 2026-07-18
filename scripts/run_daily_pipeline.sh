#!/usr/bin/env bash
set -euo pipefail

WEB_DIR="${HNDAILY_WEB_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
JSON_ROOT="${HNDAILY_JSON_ROOT:-$WEB_DIR/data/json}"
RAW_DIR="${HNDAILY_DATA_DIR:-$JSON_ROOT/raw}"
MODEL_INPUT_DIR="$JSON_ROOT/model-input"
MODEL_OUTPUT_DIR="$JSON_ROOT/model-output"
AUDIT_DIR="$JSON_ROOT/audits"
DATE_ARG="${HNDAILY_DATE:-}"

mkdir -p "$RAW_DIR" "$MODEL_INPUT_DIR" "$MODEL_OUTPUT_DIR" "$AUDIT_DIR" "$WEB_DIR/data/tmp"

if [ -z "${HNDAILY_RAW_JSON:-}" ]; then
  if [ -n "$DATE_ARG" ]; then
    RAW_JSON="$(HNDAILY_DATA_DIR="$RAW_DIR" python3 "$WEB_DIR/scripts/crawler.py" "$DATE_ARG")"
  else
    RAW_JSON="$(HNDAILY_DATA_DIR="$RAW_DIR" python3 "$WEB_DIR/scripts/crawler.py")"
  fi
else
  RAW_JSON="$HNDAILY_RAW_JSON"
fi

DATE_STEM="$(basename "$RAW_JSON" .json)"
MODEL_INPUT_JSON="$MODEL_INPUT_DIR/$DATE_STEM.json"
MODEL_OUTPUT_JSON="$MODEL_OUTPUT_DIR/$DATE_STEM.json"
PREFILTER_JSON="$AUDIT_DIR/$DATE_STEM.prefilter.json"
EDITORIAL_AUDIT_JSON="$AUDIT_DIR/$DATE_STEM.editorial-audit.json"

python3 "$WEB_DIR/scripts/prepare_model_input.py" "$RAW_JSON" "$MODEL_INPUT_JSON" "$PREFILTER_JSON" >/dev/null

echo "RAW_JSON=$RAW_JSON"
echo "MODEL_INPUT_JSON=$MODEL_INPUT_JSON"
echo "MODEL_OUTPUT_JSON=$MODEL_OUTPUT_JSON"
echo "PREFILTER_JSON=$PREFILTER_JSON"
echo "EDITORIAL_AUDIT_JSON=$EDITORIAL_AUDIT_JSON"
