#!/usr/bin/env bash
# Interval frames while the watch page is up.
# Usage: tools/jevlab/frames.sh <run_dir> [interval_s=60]
set -euo pipefail
RUN_DIR="$(readlink -f "${1:?run_dir}")"
INTERVAL="${2:-60}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
export DISPLAY="${DISPLAY:-:0}"
export GDK_BACKEND=x11
AUTH="$(ps -ww -C Xwayland -o args= 2>/dev/null | sed -n 's/.*-auth \([^ ]*\).*/\1/p' | head -1 || true)"
if [[ -n "$AUTH" && -f "$AUTH" ]]; then
  export XAUTHORITY="$AUTH"
fi
export PYTHONPATH="${REPO}/src${PYTHONPATH:+:$PYTHONPATH}"
PID_FILE="$RUN_DIR/watch/PID"
while [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; do
  python3 - <<PY
from flycast.jevlab.state import frame
frame(r"$RUN_DIR", "interval")
PY
  sleep "$INTERVAL"
done
