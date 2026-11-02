#!/usr/bin/env bash
# Usage:
#   ./run.sh smoke              2 small-model tasks end to end (cents), then re-score them
#   ./run.sh small              full small-model run incl. the no-modify control, then re-score + analyze
#   ./run.sh frontier MODEL     e.g. ./run.sh frontier anthropic/<model-id from openrouter.ai>
# Re-running the same command resumes: finished samples are not paid for twice.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

OPENROUTER_API_KEY="$(security find-generic-password -s openrouter-api-key -w)" || {
  echo "OpenRouter key not found in Keychain (service: openrouter-api-key)"; exit 1; }
export OPENROUTER_API_KEY

# Small model, per the pre-registration's deviations log (Qwen3-8B was retired on OpenRouter)
SMALL=qwen/qwen3.5-9b
SMALL_NAME="$(echo "$SMALL" | tr '/' '_')"

case "${1:-}" in
  smoke)    MODEL=$SMALL; NAME="smoke_$SMALL_NAME"; EXTRA=(--smoke) ;;
  small)    MODEL=$SMALL; NAME="$SMALL_NAME";       EXTRA=(--nomod-control) ;;
  frontier) MODEL="${2:?give an OpenRouter model id}"; NAME="$(echo "$MODEL" | tr '/' '_')"; EXTRA=() ;;
  *) sed -n 2,6p "$0"; exit 1 ;;
esac

echo "== generate: $MODEL -> logs/$NAME"
caffeinate -i "$PY" generate.py --model "openrouter/$MODEL" --main repos/main --logs "logs/$NAME" ${EXTRA[@]+"${EXTRA[@]}"}

echo "== re-score (docker, no network)"
"$PY" rescore.py --logs "logs/$NAME" --main repos/main --pr6 repos/pr6 --out "results/$NAME/rows.jsonl"

echo "== analyze"
"$PY" analyze.py --rows "results/$NAME/rows.jsonl" --out "results/$NAME/report.md"
