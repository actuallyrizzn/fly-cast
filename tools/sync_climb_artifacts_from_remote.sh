#!/usr/bin/env bash
# Pull Fly Cast climb artifacts off a time-boxed BitLaunch box onto this machine.
# Run from home (sz1/Termux) on a loop while Ada's 24h destroy clock ticks.
#
#   export FLYCAST_REMOTE='root@IP'
#   export FLYCAST_SSH_PASS_FILE=~/.ssh/flycast-climb.pass   # or use key
#   bash tools/sync_climb_artifacts_from_remote.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="${FLYCAST_REMOTE:?set FLYCAST_REMOTE=user@host}"
REMOTE_DIR="${FLYCAST_REMOTE_DIR:-/root/fly-cast/artifacts/reaction-climb}"
LOCAL_DIR="${FLYCAST_LOCAL_DIR:-$ROOT/artifacts/reaction-climb}"
INTERVAL="${FLYCAST_SYNC_INTERVAL:-120}"
PASS_FILE="${FLYCAST_SSH_PASS_FILE:-}"

mkdir -p "$LOCAL_DIR"

rsync_once() {
  local opts=(-az --partial --timeout=30)
  if [[ -n "$PASS_FILE" && -f "$PASS_FILE" ]]; then
    sshpass -f "$PASS_FILE" rsync -e "ssh -o StrictHostKeyChecking=accept-new" \
      "${opts[@]}" "${REMOTE}:${REMOTE_DIR}/" "$LOCAL_DIR/"
  else
    rsync -e "ssh -o StrictHostKeyChecking=accept-new" \
      "${opts[@]}" "${REMOTE}:${REMOTE_DIR}/" "$LOCAL_DIR/"
  fi
}

echo "sync loop → $LOCAL_DIR from ${REMOTE}:${REMOTE_DIR} every ${INTERVAL}s"
while true; do
  stamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if rsync_once; then
    echo "[$stamp] ok $(ls -1 "$LOCAL_DIR" 2>/dev/null | wc -l) files"
  else
    echo "[$stamp] sync failed (box down or not ready yet)"
  fi
  sleep "$INTERVAL"
done
