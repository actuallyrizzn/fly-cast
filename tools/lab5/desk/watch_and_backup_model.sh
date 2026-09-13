#!/usr/bin/env bash
# Watch FlyBrain for finished Lab 5/Lab 6 fly_model.npz; verify + copy to local + NewDev.
# Runs on Otto host (has fly-brain.pass + newdev2.pass). Idempotent.
set -euo pipefail
FB_PASS="${FB_PASS:-$HOME/.ssh/fly-brain.pass}"
ND_PASS="${ND_PASS:-$HOME/.ssh/newdev2.pass}"
SSH=(sshpass -f "$FB_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=20 fly-brain)
SCP=(sshpass -f "$FB_PASS" scp -o StrictHostKeyChecking=no -o ConnectTimeout=20)
LOCAL_ROOT="${LOCAL_ROOT:-/root/projects/fly-cast/artifacts}"
ND_ROOT="${ND_ROOT:-/root/fly-cast-model-backup}"
LOG="${LOG:-/root/projects/fly-cast/artifacts/corpus-gen/model-backup-watch.log}"
STATE="${STATE:-/root/projects/fly-cast/artifacts/corpus-gen/model-backup-watch.state}"
mkdir -p "$(dirname "$LOG")" "$LOCAL_ROOT" "$STATE"
POLL="${POLL:-30}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"; }

backup_one() {
  local remote_dir="$1" label="$2"
  local stamp remote_npz remote_tok local_dir sha
  remote_npz="$remote_dir/fly_model.npz"
  remote_tok="$remote_dir/tokenizer.json"
  # already backed up this path?
  if [ -f "$STATE/$label.sha256" ]; then
    local prev remote_sha
    prev=$(cat "$STATE/$label.sha256")
    remote_sha=$("${SSH[@]}" "sha256sum '$remote_npz'" | awk '{print $1}')
    if [ "$prev" = "$remote_sha" ] && [ -f "$LOCAL_ROOT/$label/fly_model.npz" ]; then
      return 0
    fi
  fi
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  local_dir="$LOCAL_ROOT/$label"
  mkdir -p "$local_dir" "$local_dir/history"
  log "FOUND $label at $remote_npz — pulling"
  "${SCP[@]}" "fly-brain:$remote_npz" "$local_dir/fly_model.npz"
  "${SCP[@]}" "fly-brain:$remote_tok" "$local_dir/tokenizer.json" 2>/dev/null || true
  # also pull LATEST pointer + summary if present
  "${SCP[@]}" "fly-brain:$remote_dir/../LATEST" "$local_dir/LATEST" 2>/dev/null || true
  "${SCP[@]}" "fly-brain:$remote_dir/summary.json" "$local_dir/summary.json" 2>/dev/null || true
  sha=$(sha256sum "$local_dir/fly_model.npz" | awk '{print $1}')
  bytes=$(stat -c%s "$local_dir/fly_model.npz")
  if [ "$bytes" -lt 1000 ]; then
    log "FATAL $label local copy too small ($bytes bytes)"
    return 1
  fi
  cp -a "$local_dir/fly_model.npz" "$local_dir/history/fly_model-$stamp.npz"
  cp -a "$local_dir/tokenizer.json" "$local_dir/history/tokenizer-$stamp.json" 2>/dev/null || true
  echo "$sha" > "$STATE/$label.sha256"
  echo "$remote_dir" > "$STATE/$label.remote_dir"
  log "LOCAL OK $label bytes=$bytes sha256=$sha → $local_dir"

  # NewDev off-box copy
  if [ -f "$ND_PASS" ]; then
    sshpass -f "$ND_PASS" ssh -o StrictHostKeyChecking=no NewDev "mkdir -p $ND_ROOT/$label/history"
    sshpass -f "$ND_PASS" scp -o StrictHostKeyChecking=no \
      "$local_dir/fly_model.npz" "$local_dir/tokenizer.json" \
      "root@64.95.11.220:$ND_ROOT/$label/" 2>/dev/null \
      || sshpass -f "$ND_PASS" scp -o StrictHostKeyChecking=no \
           "$local_dir/fly_model.npz" "NewDev:$ND_ROOT/$label/"
    sshpass -f "$ND_PASS" ssh -o StrictHostKeyChecking=no NewDev \
      "cp -a $ND_ROOT/$label/fly_model.npz $ND_ROOT/$label/history/fly_model-$stamp.npz; sha256sum $ND_ROOT/$label/fly_model.npz"
    log "NEWDEV OK $label → $ND_ROOT/$label"
  else
    log "WARN no newdev2.pass — local copy only for $label"
  fi

  # Point ~/talk at this if desk
  if [ "$label" = "lab5-desk" ] && [ -x /root/talk ]; then
    log "talk CLI: ~/talk --run $local_dir"
  fi
  return 0
}

check_lab5_failure() {
  # Process gone + DONE/saved missing → scream
  local alive done savewarn npz
  alive=$("${SSH[@]}" 'pgrep -f "lab4_run.py --train artifacts/lab5" >/dev/null && echo 1 || echo 0' || echo '?')
  if [ "$alive" != "0" ]; then return 0; fi
  done=$("${SSH[@]}" 'grep -c "DONE Lab4\|saved .*fly_model" /root/fly-cast/artifacts/lab5/desk/lab5-desk-run.log 2>/dev/null || true')
  savewarn=$("${SSH[@]}" 'grep -c "save warn" /root/fly-cast/artifacts/lab5/desk/lab5-desk-run.log 2>/dev/null || true')
  npz=$("${SSH[@]}" 'find /root/fly-cast/artifacts/lab5/desk -name fly_model.npz 2>/dev/null | head -1')
  if [ -z "$npz" ]; then
    log "ALERT Lab5 process dead and NO fly_model.npz on FlyBrain (done_hits=$done save_warn=$savewarn)"
    echo "MISSING" > "$STATE/lab5-desk.ALERT"
  fi
}

log "watch started poll=${POLL}s"
while true; do
  # Resolve LATEST or any run dir with fly_model.npz
  mapfile -t hits < <("${SSH[@]}" 'find /root/fly-cast/artifacts/lab5/desk /root/fly-cast/artifacts/lab6 -name fly_model.npz 2>/dev/null' || true)
  for npz in "${hits[@]:-}"; do
    [ -z "$npz" ] && continue
    dir=$(dirname "$npz")
    case "$dir" in
      */lab5/desk/*) backup_one "$dir" "lab5-desk" || true ;;
      */lab6/*)      backup_one "$dir" "lab6-clonehero" || true ;;
      *)             backup_one "$dir" "lab-other" || true ;;
    esac
  done
  check_lab5_failure || true
  sleep "$POLL"
done
