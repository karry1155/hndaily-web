#!/usr/bin/env bash
set -euo pipefail
WEB_DIR="${HNDAILY_WEB_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SKILL_DIR="${HNDAILY_SKILL_DIR:-/Users/skr/Work/hndaily/hndaily-skill}"
DATE_ARG="${1:-}"; INTERMEDIATE_DIR="${HNDAILY_INTERMEDIATE_DIR:-$WEB_DIR/data/intermediate}"
CONTENT_ROOT="${RADAR_CONTENT_ROOT:-$WEB_DIR/content}"; SITE_ROOT="${RADAR_SITE_ROOT:-$WEB_DIR/site}"; AS_OF="${RADAR_AS_OF:-$(date +%F)}"
mkdir -p "$INTERMEDIATE_DIR"
if [ -n "${HNDAILY_RAW_JSON:-}" ]; then RAW_JSON="$HNDAILY_RAW_JSON"; elif [ -n "$DATE_ARG" ]; then RAW_JSON="$(python3 "$SKILL_DIR/crawler.py" "$DATE_ARG")"; else RAW_JSON="$(python3 "$SKILL_DIR/crawler.py")"; fi
DATE_STEM="$(basename "$RAW_JSON" .json)"; MODEL_INPUT_JSON="$INTERMEDIATE_DIR/$DATE_STEM.radar-model-input.json"
MODEL_OUTPUT_JSON="${RADAR_MODEL_OUTPUT_JSON:-$INTERMEDIATE_DIR/$DATE_STEM.radar-model-output.json}"; PREFILTER_JSON="$INTERMEDIATE_DIR/$DATE_STEM.radar-prefilter.json"; AUDIT_JSON="$INTERMEDIATE_DIR/$DATE_STEM.radar-audit.json"
RUN_ROOT="${RADAR_RUN_ROOT:-$WEB_DIR/data/tmp/radar-$DATE_STEM}"; STAGED_CONTENT="$RUN_ROOT/content"; STAGED_SITE="$RUN_ROOT/site"; STAGED_AUDIT="$RUN_ROOT/audit.json"
python3 "$WEB_DIR/scripts/prepare_radar.py" "$RAW_JSON" "$MODEL_INPUT_JSON" "$PREFILTER_JSON" >/dev/null
printf 'RAW_JSON=%s\nMODEL_INPUT_JSON=%s\nMODEL_OUTPUT_JSON=%s\nPREFILTER_JSON=%s\nAUDIT_JSON=%s\n' "$RAW_JSON" "$MODEL_INPUT_JSON" "$MODEL_OUTPUT_JSON" "$PREFILTER_JSON" "$AUDIT_JSON"
if [ ! -s "$MODEL_OUTPUT_JSON" ]; then echo "STATUS=MODEL_OUTPUT_REQUIRED"; exit 2; fi
python3 "$WEB_DIR/scripts/radar_transaction.py" prepare "$CONTENT_ROOT" "$STAGED_CONTENT"
python3 "$WEB_DIR/scripts/finalize_radar.py" "$RAW_JSON" "$MODEL_INPUT_JSON" "$MODEL_OUTPUT_JSON" "$STAGED_CONTENT" "$STAGED_AUDIT" "$AS_OF"
python3 "$WEB_DIR/scripts/radar_render.py" "$STAGED_CONTENT" "$STAGED_SITE"
python3 "$WEB_DIR/scripts/radar_transaction.py" publish "$CONTENT_ROOT" "$STAGED_CONTENT" "$SITE_ROOT" "$STAGED_SITE" "$AUDIT_JSON" "$STAGED_AUDIT"
echo "STATUS=COMPLETE"
