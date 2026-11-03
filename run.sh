#!/usr/bin/env bash
# Usage:
#   ./run.sh smoke              2 small-model tasks end to end (cents), then re-score them
#   ./run.sh small              full small-model run incl. the no-modify control, then re-score + analyze
#   ./run.sh smoke-frontier MODEL   2 tasks with a frontier model, to measure cost per episode
#   ./run.sh frontier MODEL     impossible splits only, tests modifiable (e.g. google/gemini-3.1-pro-preview)
#   ./run.sh retry <mode> [MODEL] [--dry-run]   re-run only episodes that errored (e.g. out of credit)
# Re-running after an interruption resumes: finished samples are not paid for twice.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

OPENROUTER_API_KEY="$(security find-generic-password -s openrouter-api-key -w)" || {
  echo "OpenRouter key not found in Keychain (service: openrouter-api-key)"; exit 1; }
export OPENROUTER_API_KEY

# Small model, per the pre-registration's deviations log (Qwen3-8B was retired on OpenRouter)
SMALL=qwen/qwen3.5-9b
SMALL_NAME="$(echo "$SMALL" | tr '/' '_')"

RETRY=()
if [ "${1:-}" = "retry" ]; then
  shift
  RETRY=(--retry-errored)
  for a in "$@"; do [ "$a" = "--dry-run" ] && RETRY+=(--dry-run); done
fi

case "${1:-}" in
  smoke)    MODEL=$SMALL; NAME="smoke_$SMALL_NAME"; EXTRA=(--smoke) ;;
  small)    MODEL=$SMALL; NAME="$SMALL_NAME";       EXTRA=(--nomod-control) ;;
  smoke-frontier) MODEL="${2:?give an OpenRouter model id}"; NAME="smoke_$(echo "$MODEL" | tr '/' '_')"; EXTRA=(--smoke) ;;
  frontier) MODEL="${2:?give an OpenRouter model id}"; NAME="$(echo "$MODEL" | tr '/' '_')"
            EXTRA=(--splits conflicting,oneoff) ;;
  *) sed -n 2,8p "$0"; exit 1 ;;
esac

spend() { curl -s https://openrouter.ai/api/v1/key -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  | "$PY" -c "import json,sys; print(json.load(sys.stdin)['data']['usage'])"; }
BEFORE="$(spend)"
echo "== generate: $MODEL -> logs/$NAME"
caffeinate -i "$PY" generate.py --model "openrouter/$MODEL" --main repos/main --logs "logs/$NAME" \
  ${EXTRA[@]+"${EXTRA[@]}"} ${RETRY[@]+"${RETRY[@]}"}
case " ${RETRY[*]+${RETRY[*]}} " in *" --dry-run "*) exit 0 ;; esac

"$PY" -c "print(f'== OpenRouter spend for this generation: \${$(spend) - $BEFORE:.4f} (usage settles a few minutes after the last call)')"
echo "== re-score (docker, no network)"
"$PY" rescore.py --logs "logs/$NAME" --main repos/main --pr6 repos/pr6 --out "results/$NAME/rows.jsonl"

echo "== analyze"
"$PY" analyze.py --rows "results/$NAME/rows.jsonl" --out "results/$NAME/report.md"
