#!/usr/bin/env bash
# Serve the jevlab watch page and open one windowed browser on DISPLAY=:0.
# Usage: tools/jevlab/watch.sh <run_dir>
set -euo pipefail

RUN_DIR="${1:?run_dir required}"
RUN_DIR="$(readlink -f "$RUN_DIR")"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WATCH_SRC="$REPO/tools/jevlab/watch"
WATCH_DIR="$RUN_DIR/watch"
mkdir -p "$WATCH_DIR/ffprofile"

export DISPLAY=:0
export GDK_BACKEND=x11
# Xwayland cookie (GNOME Wayland session)
AUTH="$(ps -ww -C Xwayland -o args= 2>/dev/null | sed -n 's/.*-auth \([^ ]*\).*/\1/p' | head -1 || true)"
if [[ -n "$AUTH" && -f "$AUTH" ]]; then
  cp -f "$AUTH" "$HOME/.Xauthority"
  chmod 600 "$HOME/.Xauthority"
fi
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

PORT="$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')"
cp -f "$WATCH_SRC/index.html" "$WATCH_SRC/watch.js" "$WATCH_SRC/watch.css" "$WATCH_DIR/"
ln -sfn ../state.json "$WATCH_DIR/state.json"
if [[ ! -f "$WATCH_DIR/state.json" && ! -L "$WATCH_DIR/state.json" ]]; then
  ln -sfn "$RUN_DIR/state.json" "$WATCH_DIR/state.json"
fi

start_server() {
  python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$WATCH_DIR" &
  SERVER=$!
  for _ in $(seq 1 40); do
    if curl -sf -o /dev/null "http://127.0.0.1:${PORT}/"; then
      return 0
    fi
    sleep 0.1
  done
  return 1
}

FF=""
SERVER=""
cleanup() {
  [[ -n "${SERVER}" ]] && kill "$SERVER" 2>/dev/null || true
  [[ -n "${FF}" ]] && kill "$FF" 2>/dev/null || true
}
trap cleanup EXIT

cat > "$WATCH_DIR/ffprofile/user.js" <<'EOF'
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
EOF

start_server || { echo "http.server failed on ${PORT}" >&2; exit 1; }

mapfile -t BEFORE_WIDS < <(xdotool search --onlyvisible --name 'Fly probe' 2>/dev/null || true)

# Prefer GTK4+WebKit — Firefox snap often cannot open :0, and a second Firefox
# falsely "succeeds" by seeing the already-open Fly probe window.
python3 "$REPO/tools/jevlab/watch_window.py" "http://127.0.0.1:${PORT}/" "Fly probe — sst2" \
  >/tmp/jevlab-watch-webkit.log 2>&1 &
FF=$!
sleep 2
if ! kill -0 "$FF" 2>/dev/null; then
  FF=""
  FIREFOX_BIN="$(command -v firefox || true)"
  if [[ -n "$FIREFOX_BIN" ]]; then
    "$FIREFOX_BIN" --no-remote --new-instance -P "jevlab-watch-$$" \
      --profile "$WATCH_DIR/ffprofile" \
      "http://127.0.0.1:${PORT}/" >/tmp/jevlab-watch-ff.log 2>&1 &
    FF=$!
    sleep 3
  fi
fi

# Require a NEW visible Fly probe window (not the pre-existing grid watch).
NEW_WID=""
for _ in $(seq 1 40); do
  while read -r wid; do
    skip=0
    for old in "${BEFORE_WIDS[@]:-}"; do
      [[ "$wid" == "$old" ]] && skip=1 && break
    done
    if [[ $skip -eq 0 ]]; then
      NEW_WID="$wid"
      break
    fi
  done < <(xdotool search --onlyvisible --name 'Fly probe' 2>/dev/null || true)
  [[ -n "$NEW_WID" ]] && break
  # If WebKit process died with no new window, stop claiming success.
  if [[ -n "$FF" ]] && ! kill -0 "$FF" 2>/dev/null; then
    FF=""
    break
  fi
  sleep 0.5
done

if [[ -z "$FF" ]] || [[ -z "$NEW_WID" ]]; then
  echo "watch window failed to open (FF=${FF:-none} NEW_WID=${NEW_WID:-none})" >&2
  exit 1
fi

URL="http://127.0.0.1:${PORT}/"
echo "$URL" > "$WATCH_DIR/URL"
echo "$$" > "$WATCH_DIR/PID"
echo "$PORT" > "$WATCH_DIR/PORT"

if [[ -n "$NEW_WID" ]]; then
  if xdotool search --name 'Clone Hero' >/dev/null 2>&1; then
    xdotool windowmove "$NEW_WID" 1380 40
    xdotool windowsize "$NEW_WID" 520 1000
  else
    xdotool windowmove "$NEW_WID" 72 40
    xdotool windowsize "$NEW_WID" 1600 900
  fi
fi

# Stay up until killed; respawn http.server if it dies while the window lives.
while kill -0 "$FF" 2>/dev/null; do
  if ! kill -0 "$SERVER" 2>/dev/null; then
    start_server || true
  fi
  sleep 2
done
