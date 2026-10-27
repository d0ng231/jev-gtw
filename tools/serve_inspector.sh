#!/usr/bin/env bash
# Run in an environment containing the official StartLux inference package.
set -euo pipefail
MODEL_ID=startlux-models/StartLux-Decision-v1.1-0.8B-Instant
MODEL_REVISION=6496ae641cc71b149ce9dad69bd97f2a44e7bf11
MODEL_DIR="${JEV_GTW_MODEL_DIR:-models/StartLux-Decision-v1.1-0.8B-Instant}"
: "${TMPDIR:?Set TMPDIR to your private scratch directory}"
hf download "$MODEL_ID" --revision "$MODEL_REVISION" --local-dir "$MODEL_DIR"
exec startlux-decide serve --model "$MODEL_DIR" --host 127.0.0.1 \
  --port "${JEV_GTW_PORT:-8090}" --launch-vllm --gpus "${JEV_GTW_GPUS:-0}" \
  --max-images 1 --max-model-len 8192 --no-none-check
