#!/usr/bin/env bash
# Research tools (Agent-Reach + yt-dlp) in their own venv, kept apart from the pinned voice/torch venv.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -x .venv-tools/bin/python ] || python3 -m venv .venv-tools
# The GitHub archive URL is blocked by the proxy; install from a clone instead.
SRC="${TMPDIR:-/tmp}/agent-reach"
[ -d "$SRC" ] || git clone -q --depth 1 https://github.com/Panniantong/agent-reach.git "$SRC"
.venv-tools/bin/pip install -q "$SRC" "yt-dlp[default]"
.venv-tools/bin/agent-reach doctor
