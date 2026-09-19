#!/usr/bin/env bash
# Rsync a run bundle off the laptop (no cache).
# Usage: tools/jevlab/sync_run.sh <run_dir> [dest]
set -euo pipefail
RUN_DIR="$(readlink -f "${1:?run_dir}")"
DEST="${2:-/root/fly-cast-runs/jevlab/runs/$(basename "$RUN_DIR")}"
mkdir -p "$DEST"
rsync -a \
  --exclude='cache/' \
  --exclude='watch/ffprofile/' \
  --exclude='*.npy' \
  "$RUN_DIR/" "$DEST/"
echo "synced $RUN_DIR -> $DEST"
