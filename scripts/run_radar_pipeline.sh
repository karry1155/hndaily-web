#!/usr/bin/env bash
set -euo pipefail
WEB_DIR="${HNDAILY_WEB_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
PRODUCTION_ROOT="${HNDAILY_PRODUCTION_ROOT:-$WEB_DIR/data/production-json}"
RAW_DIR="${HNDAILY_DATA_DIR:-$PRODUCTION_ROOT/source}"
MODEL_INPUT_DIR="$PRODUCTION_ROOT/input"
MODEL_OUTPUT_DIR="$PRODUCTION_ROOT/enrichment"
AUDIT_DIR="$PRODUCTION_ROOT/audit"
DATE_ARG="${1:-}"
CONTENT_ROOT="${RADAR_CONTENT_ROOT:-$WEB_DIR/content}"
SITE_ROOT="${RADAR_SITE_ROOT:-$WEB_DIR/site}"
mkdir -p "$RAW_DIR" "$MODEL_INPUT_DIR" "$MODEL_OUTPUT_DIR" "$AUDIT_DIR"

if [ -n "${HNDAILY_RAW_JSON:-}" ]; then
  RAW_JSON="$HNDAILY_RAW_JSON"
elif [ -n "$DATE_ARG" ]; then
  RAW_JSON="$(HNDAILY_DATA_DIR="$RAW_DIR" python3 "$WEB_DIR/scripts/crawler.py" "$DATE_ARG")"
else
  RAW_JSON="$(HNDAILY_DATA_DIR="$RAW_DIR" python3 "$WEB_DIR/scripts/crawler.py")"
fi

DATE_STEM="$(basename "$RAW_JSON" .json)"
MODEL_INPUT_JSON="$MODEL_INPUT_DIR/$DATE_STEM.json"
MODEL_OUTPUT_JSON="${RADAR_MODEL_OUTPUT_JSON:-$MODEL_OUTPUT_DIR/$DATE_STEM.json}"
PROMPT_DIR="$WEB_DIR/prompts/article-enrichment/v2"
PREFILTER_JSON="$AUDIT_DIR/$DATE_STEM.prefilter.json"
AUDIT_JSON="${RADAR_AUDIT_JSON:-$AUDIT_DIR/$DATE_STEM.publication.json}"
RUN_ROOT="${RADAR_RUN_ROOT:-$WEB_DIR/data/tmp/radar-$DATE_STEM}"
STAGED_CONTENT="$RUN_ROOT/content"
STAGED_SITE="$RUN_ROOT/site"
STAGED_AUDIT="$RUN_ROOT/audit.json"
python3 "$WEB_DIR/scripts/prepare_radar.py" "$RAW_JSON" "$MODEL_INPUT_JSON" "$PREFILTER_JSON" >/dev/null
printf 'RAW_JSON=%s\nMODEL_INPUT_JSON=%s\nMODEL_OUTPUT_JSON=%s\nPROMPT_DIR=%s\nPREFILTER_JSON=%s\nAUDIT_JSON=%s\n' "$RAW_JSON" "$MODEL_INPUT_JSON" "$MODEL_OUTPUT_JSON" "$PROMPT_DIR" "$PREFILTER_JSON" "$AUDIT_JSON"
if [ ! -s "$MODEL_OUTPUT_JSON" ]; then echo "STATUS=MODEL_OUTPUT_REQUIRED"; exit 2; fi
if ! python3 "$WEB_DIR/scripts/check_model_output.py" "$MODEL_INPUT_JSON" "$MODEL_OUTPUT_JSON"; then
  echo "STATUS=MODEL_OUTPUT_REQUIRED"
  exit 2
fi
python3 "$WEB_DIR/scripts/radar_transaction.py" prepare "$CONTENT_ROOT" "$STAGED_CONTENT"
python3 "$WEB_DIR/scripts/finalize_radar.py" "$RAW_JSON" "$MODEL_INPUT_JSON" "$MODEL_OUTPUT_JSON" "$STAGED_CONTENT" "$STAGED_AUDIT"
python3 "$WEB_DIR/scripts/radar_render.py" "$STAGED_CONTENT" "$STAGED_SITE"
python3 "$WEB_DIR/scripts/radar_transaction.py" publish "$CONTENT_ROOT" "$STAGED_CONTENT" "$SITE_ROOT" "$STAGED_SITE" "$AUDIT_JSON" "$STAGED_AUDIT"
echo "STATUS=COMPLETE"
