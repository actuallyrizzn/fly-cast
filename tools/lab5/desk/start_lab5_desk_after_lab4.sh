#!/usr/bin/env bash
# FlyBrain: wait for Lab 4 (lab4_run.py) to exit, then start the Lab 5 desk run + chronicle sidecar.
# Idempotent: refuses to start if a desk run is already alive.
set -uo pipefail
cd /root/fly-cast
LOG=/root/fly-cast/artifacts/lab5/desk/lab5-desk-run.log
mkdir -p artifacts/lab5/desk
PY=${PY:-/root/fly-cast/.venv/bin/python}
[ -x "$PY" ] || PY=python3

if pgrep -f "tools/lab4/lab4_run.py --train artifacts/lab5" >/dev/null; then
  echo "desk run already alive"; exit 0
fi
echo "[$(date -u +%FT%TZ)] waiting for Lab 4 to exit…" | tee -a "$LOG"
while pgrep -f "python -u tools/lab4/lab4_run.py$" >/dev/null || pgrep -fx "python -u tools/lab4/lab4_run.py" >/dev/null; do sleep 60; done
echo "[$(date -u +%FT%TZ)] Lab 4 gone; starting Lab 5 desk" | tee -a "$LOG"

# retire the Lab 4 sidecar so two chronicles don't fight for the CLI agent
pkill -f "lab4_progress_chronicle.py --interval" 2>/dev/null || true
sleep 2

nohup "$PY" -u tools/lab4/lab4_run.py \
  --train artifacts/lab5/desk/data/train.txt \
  --valid artifacts/lab5/desk/data/valid.txt \
  --heldout artifacts/lab5/desk/data/heldout.txt \
  --floors artifacts/lab5/desk/baselines.json \
  --softmax-a-epochs 3 --level-b-epochs 4 \
  --level-c-epochs 5 --pairs-per-epoch 80000 --scramble-pairs-per-epoch 45000 \
  --out-root artifacts/lab5/desk \
  >> "$LOG" 2>&1 &
echo "lab5 pid=$!" | tee -a "$LOG"
sleep 5
nohup "$PY" -u tools/lab4/lab4_progress_chronicle.py \
  --log "$LOG" --doc-id 1334 --label "Lab 5 Desk go/no-go" \
  --state artifacts/lab5/desk/progress-chronicle.state.json \
  --pgrep "lab4_run.py --train artifacts/lab5" \
  --interval 60 --grok-every 2 \
  >> artifacts/lab5/desk/progress-chronicle.log 2>&1 &
echo "chronicle pid=$!" | tee -a "$LOG"
