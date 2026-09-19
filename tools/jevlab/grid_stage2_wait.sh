#!/usr/bin/env bash
# Wait for sst2 stage1 to finish cleanly, then run stage2.
# Requires: stage1.jsonl >= 1458 lines, no stage-1 grid process, and
# "grid stage 1 done=" in stage1.log (avoids restart-race false starts).
set -euo pipefail
ROOT="${JEVLAB_ROOT:-$HOME/fly-cast-runs/jevlab}"
TASK_DIR="$ROOT/grid/sst2"
STAGE1="$TASK_DIR/stage1.jsonl"
STAGE1_LOG="$TASK_DIR/stage1.log"
LOG="$ROOT/logs/stage2-waiter.log"
CAST="${FLYCAST_REPO:-$HOME/fly-cast}"
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) waiter start"
while true; do
  n=0
  if [[ -f "$STAGE1" ]]; then
    n=$(wc -l < "$STAGE1" | tr -d ' ')
  fi
  if pgrep -f 'tools/jevlab/grid.py --task sst2 --stage 1' >/dev/null 2>&1; then
    running=1
  else
    running=0
  fi
  done_marker=0
  if [[ -f "$STAGE1_LOG" ]] && grep -q 'grid stage 1 done=' "$STAGE1_LOG"; then
    done_marker=1
  fi
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) stage1_lines=$n running=$running done_marker=$done_marker"
  if [[ "$n" -ge 1458 && "$running" -eq 0 && "$done_marker" -eq 1 ]]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) launching stage2"
    cd "$CAST"
    # shellcheck disable=SC1091
    . .venv/bin/activate
    {
      echo "jevlab-grid-sst2-stage2"
      echo "grid stage 2 fine"
      echo "starting"
      echo "elapsed 0"
      echo "top-10 x 3 seeds per arm"
    } > "$HOME/fly-cast-runs/desk_status.txt"
    python -u tools/jevlab/grid.py --task sst2 --stage 2 --root "$ROOT" --resume --watch-dir "$ROOT/runs/grid-watch"
    rc=$?
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) stage2 exit=$rc"
    touch "$ROOT/RESTORE_POWERSAVE_AFTER_GRID"
    exit "$rc"
  fi
  sleep 60
done
