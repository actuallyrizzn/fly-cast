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

python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$WATCH_DIR" &
SERVER=$!

FF=""
cleanup() {
  kill "$SERVER" 2>/dev/null || true
  if [[ -n "${FF}" ]]; then
    kill "$FF" 2>/dev/null || true
  fi
}
trap cleanup EXIT

cat > "$WATCH_DIR/ffprofile/user.js" <<'EOF'
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
EOF

# Prefer Firefox; fall back to GTK4+WebKit (Firefox snap cannot open :0 here).
FIREFOX_BIN="$(command -v firefox || true)"
FF=""
if [[ -n "$FIREFOX_BIN" ]]; then
  "$FIREFOX_BIN" --no-remote --new-instance -P jevlab-watch \
    --profile "$WATCH_DIR/ffprofile" \
    "http://127.0.0.1:${PORT}/" >/tmp/jevlab-watch-ff.log 2>&1 &
  FF=$!
  sleep 3
  if ! xdotool search --onlyvisible --name 'Fly probe' >/dev/null 2>&1; then
    kill "$FF" 2>/dev/null || true
    FF=""
  fi
fi
if [[ -z "$FF" ]]; then
  python3 "$REPO/tools/jevlab/watch_window.py" "http://127.0.0.1:${PORT}/" "Fly probe — sst2" \
    >/tmp/jevlab-watch-webkit.log 2>&1 &
  FF=$!
fi

URL="http://127.0.0.1:${PORT}/"
echo "$URL" > "$WATCH_DIR/URL"
echo "$$" > "$WATCH_DIR/PID"
echo "$PORT" > "$WATCH_DIR/PORT"

# Wait for a window whose title starts with Fly probe
for _ in $(seq 1 40); do
  if xdotool search --onlyvisible --name 'Fly probe' >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

WID="$(xdotool search --onlyvisible --name 'Fly probe' 2>/dev/null | head -1 || true)"
if [[ -n "$WID" ]]; then
  if xdotool search --name 'Clone Hero' >/dev/null 2>&1; then
    xdotool windowmove "$WID" 1380 40
    xdotool windowsize "$WID" 520 1000
  else
    xdotool windowmove "$WID" 72 40
    xdotool windowsize "$WID" 1600 900
  fi
fi

if [[ -n "$FF" ]]; then
  wait "$FF" || true
else
  # Keep the server up until killed via PID.
  wait "$SERVER" || true
fi
