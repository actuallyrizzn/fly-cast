#!/bin/bash
# Live status window on the ngram laptop desktop. Loopback only.
set -euo pipefail
export DISPLAY="${DISPLAY:-:0}"
export GDK_BACKEND=x11

ROOT="${HOME}/fly-cast-runs/desk"
STATUS="${HOME}/fly-cast-runs/desk_status.txt"
PAGE="${ROOT}/www"
mkdir -p "$PAGE" "$ROOT"
if [[ ! -f "$STATUS" ]]; then
  printf 'waiting\nstarting the desk window\n\n0s\n\n' > "$STATUS"
fi
ln -sfn "$STATUS" "$PAGE/desk_status.txt"
python3 "$(dirname "$0")/ngram_desk_status.py" --dir "$PAGE" >/dev/null

PORT="$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')"
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$PAGE" >/tmp/ngram-desk-http.log 2>&1 &
SERVER=$!
FF=""
cleanup() {
  kill "$SERVER" 2>/dev/null || true
}
trap cleanup EXIT

PROFILE="${ROOT}/ffprofile"
mkdir -p "$PROFILE"
cat > "$PROFILE/user.js" <<'EOF'
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
EOF

if ! xdotool search --onlyvisible --name "ngram —" >/dev/null 2>&1; then
  firefox --no-remote --new-instance -P jevlab-desk --profile "$PROFILE" "http://127.0.0.1:${PORT}/" >/tmp/ngram-desk-firefox.log 2>&1 &
  FF=$!
  for _ in $(seq 1 20); do
    if xdotool search --onlyvisible --name "ngram —" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

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
echo "http://127.0.0.1:${PORT}/" | tee "${ROOT}/URL"
echo $$ > "${ROOT}/PID"
echo "$SERVER" > "${ROOT}/HTTP_PID"
# Stay up so the server lives with this process. Firefox is left running.
wait "$SERVER"
