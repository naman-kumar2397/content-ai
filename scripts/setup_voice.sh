#!/usr/bin/env bash
# Idempotent setup of Chatterbox TTS (CPU-only). Safe to re-run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3.11}"   # chatterbox-tts pins torch 2.6 / numpy<2 -> use 3.11 (or 3.10-3.12)
command -v "$PY" >/dev/null || PY=/usr/bin/python3.11

[ -x .venv/bin/python ] || "$PY" -m venv .venv
VPY=.venv/bin/python
LOG="$ROOT/.venv/setup.log"

if ! $VPY -c "import torch,sys; assert torch.__version__.startswith('2.6.0')" 2>/dev/null; then
  echo "Installing CPU torch/torchaudio 2.6.0..."
  $VPY -m pip install -q torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu >"$LOG" 2>&1 || { tail -20 "$LOG"; exit 1; }
fi
if ! $VPY -c "import chatterbox" 2>/dev/null; then
  echo "Installing chatterbox-tts..."
  $VPY -m pip install -q chatterbox-tts >>"$LOG" 2>&1 || { tail -20 "$LOG"; exit 1; }
fi

echo "Pre-downloading model weights..."
$VPY - <<'PYEOF'
from huggingface_hub import snapshot_download
p = snapshot_download(repo_id="ResembleAI/chatterbox",
    allow_patterns=["ve.safetensors","t3_cfg.safetensors","s3gen.safetensors","tokenizer.json","conds.pt"])
print("weights at", p)
PYEOF
mkdir -p output voice
echo "Done. Test: .venv/bin/python scripts/tts.py --text 'Hello.' --out output/x.wav"
