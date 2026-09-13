#!/usr/bin/env bash
# FlyBrain: after Lab 5 desk exits, start Lab 6 (Clone Hero rematch — looser B early-stop, C=10).
set -uo pipefail
cd /root/fly-cast
LOG=/root/fly-cast/artifacts/lab6/lab6-run.log
mkdir -p artifacts/lab6
PY=${PY:-/root/fly-cast/.venv/bin/python}
[ -x "$PY" ] || PY=python3

if pgrep -f "tools/lab4/lab4_run.py --out-root artifacts/lab6" >/dev/null; then
  echo "lab6 already alive"; exit 0
fi

echo "[$(date -u +%FT%TZ)] waiting for Lab 5 desk to exit…" | tee -a "$LOG"
# Lab 5 is launched as: lab4_run.py --train artifacts/lab5 ...
while pgrep -f "lab4_run.py --train artifacts/lab5" >/dev/null; do sleep 60; done
echo "[$(date -u +%FT%TZ)] Lab 5 gone; starting Lab 6 Clone Hero rematch" | tee -a "$LOG"

pkill -f "lab4_progress_chronicle.py --doc-id 1334" 2>/dev/null || true
sleep 2

# Same corpus as Lab 4; longer/looser training (Tasks Doc #1335).
nohup "$PY" -u tools/lab4/lab4_run.py \
  --softmax-a-epochs 5 \
  --level-b-epochs 8 \
  --level-c-epochs 10 \
  --pairs-per-epoch 40000 \
  --early-stop-patience-b 4 \
  --early-stop-patience-c 3 \
  --scramble-pairs-per-epoch 25000 \
  --out-root artifacts/lab6 \
  >> "$LOG" 2>&1 &
echo "lab6 pid=$!" | tee -a "$LOG"
sleep 5
nohup "$PY" -u tools/lab4/lab4_progress_chronicle.py \
  --log "$LOG" --doc-id 1336 --label "Lab 6 Clone Hero rematch" \
  --state artifacts/lab6/progress-chronicle.state.json \
  --pgrep "lab4_run.py --out-root artifacts/lab6" \
  --interval 60 --grok-every 2 \
  >> artifacts/lab6/progress-chronicle.log 2>&1 &
echo "chronicle pid=$!" | tee -a "$LOG"
