#!/bin/bash
# Live status window on the ngram laptop desktop. Loopback only.
set -euo pipefail
export DISPLAY="${DISPLAY:-:0}"
export GDK_BACKEND=x11
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
# The laptop session is Wayland. Xwayland's auth file is not ~/.Xauthority.
if [[ -z "${XAUTHORITY:-}" || ! -f "${XAUTHORITY}" ]]; then
  AUTH="$(ps -ww -C Xwayland -o args= | sed -n 's/.*-auth \([^ ]*\).*/\1/p' | head -1)"
  if [[ -n "$AUTH" && -f "$AUTH" ]]; then
    export XAUTHORITY="$AUTH"
    # Snap Firefox cannot read the mutter cookie. A copy in $HOME is for
    # xdotool. The window itself is GTK, not Firefox.
    cp "$AUTH" "${HOME}/.Xauthority"
    chmod 600 "${HOME}/.Xauthority"
    export XAUTHORITY="${HOME}/.Xauthority"
  fi
fi

ROOT="${HOME}/fly-cast-runs/desk"
STATUS="${HOME}/fly-cast-runs/desk_status.txt"
mkdir -p "$ROOT"
if [[ ! -f "$STATUS" ]]; then
  printf 'waiting\nstarting the desk window\n\n0s\n\n' > "$STATUS"
fi

python3 "$(dirname "$0")/ngram_desk_window.py" >/tmp/ngram-desk-window.log 2>&1 &
WINPID=$!
cleanup() {
  kill "$WINPID" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 20); do
  if xdotool search --onlyvisible --name "ngram —" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

WIN="$(xdotool search --onlyvisible --name "ngram —" | head -1 || true)"
if [[ -n "$WIN" ]]; then
  if xdotool search --name "Clone Hero" >/dev/null 2>&1; then
    xdotool windowmove "$WIN" 1380 40
    xdotool windowsize "$WIN" 520 1000
  else
    xdotool windowmove "$WIN" 72 40
    xdotool windowsize "$WIN" 900 700
  fi
fi
echo $$ > "${ROOT}/PID"
echo "$WINPID" > "${ROOT}/WINPID"
wait "$WINPID"
