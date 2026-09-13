#!/usr/bin/env bash
# Self-deleting FlyBrain tear-down cron payload.
# At fire time:
#   1) Broca → Ada: destroy FlyBrain (she may reply with a Mark LCPP token)
#   2) AgentMail → Mark Gmail: Ada's reply / token
#   3) Remove this cron entry (self-delete)
#
# Marker tag in crontab: FLYBRAIN_DESTROY_CRON
set -euo pipefail

LOG_DIR=/root/projects/fly-cast/artifacts/corpus-gen
LOG="$LOG_DIR/flybrain-ada-destroy-cron.log"
mkdir -p "$LOG_DIR"
exec >>"$LOG" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] cron fire start"

SERVER_ID=6aa4aa62c9c98a4525087c18
SERVER_NAME=FlyBrain
SERVER_IP=64.94.84.114
DESTROY_AT=2026-09-13T01:27:00Z
MARK_GMAIL=rizzn.dourden@gmail.com
BROCA_PY=/root/projects/sanctum/scripts/otto_ada_broca.py
SSH_PASS=/root/.ssh/athena-moya.pass
ADA_ENV=/root/.config/broca/ada.env
AGENTMAIL_PASS=/root/.ssh/agentmail-ottovernal.pass
OUTBOX_TXT="$LOG_DIR/flybrain-ada-destroy-outbox.txt"
MAIL_BODY="$LOG_DIR/flybrain-ada-destroy-mailbody.txt"

cleanup_cron() {
  local tmp
  tmp="$(mktemp)"
  crontab -l 2>/dev/null | grep -v 'FLYBRAIN_DESTROY_CRON' >"$tmp" || true
  crontab "$tmp" || true
  rm -f "$tmp"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] cron entry removed (self-delete)"
}
trap cleanup_cron EXIT

# --- 1) Tunnel + Broca message Ada ---
sshpass -f "$SSH_PASS" ssh -o StrictHostKeyChecking=no -f -N \
  -L 127.0.0.1:8872:127.0.0.1:8872 moya 2>/dev/null || true
sleep 2
set -a
# shellcheck disable=SC1090
. "$ADA_ENV"
set +a

MSG=$(cat <<EOF
[Otto · orchestrator → ada — managed handoff]

FLYBRAIN TEAR-DOWN CRON FIRE ($(date -u +%Y-%m-%dT%H:%M:%SZ))

Please destroy BitLaunch server now:
- name: ${SERVER_NAME}
- id: ${SERVER_ID}
- ipv4: ${SERVER_IP}
- scheduled destroy window: ${DESTROY_AT}

If you need a Mark LCPP two-word token first, reply with the exact token Mark must type on Telegram — Otto will email it to his Gmail via AgentMail in this same cron fire.

If you can destroy under existing preauth, do it and confirm destroyed.
EOF
)

set +e
python3 "$BROCA_PY" --wait-timeout 600 -m "$MSG" >"$OUTBOX_TXT" 2>&1
BROCA_EC=$?
set -e
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] broca exit=$BROCA_EC"
ADA_REPLY="$(cat "$OUTBOX_TXT" 2>/dev/null || true)"
if [[ -z "$ADA_REPLY" ]]; then
  ADA_REPLY="(no Broca outbox text captured; exit=$BROCA_EC)"
fi

# --- 2) Email Mark via AgentMail → Gmail with Ada result / token ---
SUBJECT="FlyBrain destroy — Ada reply / token ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
cat >"$MAIL_BODY" <<EOF
Otto cron fire for FlyBrain tear-down.

Server: ${SERVER_NAME} (${SERVER_ID}) @ ${SERVER_IP}
Scheduled window: ${DESTROY_AT}

Ada's reply is below. If she issued a two-word LCPP token, type it verbatim to Ada on Telegram so she can destroy.

--- Ada / Broca output ---
${ADA_REPLY}
--- end ---

— Otto Vernal (AgentMail)
EOF

set -a
# shellcheck disable=SC1090
. "$AGENTMAIL_PASS"
set +a

export FLYBRAIN_MAIL_TO="$MARK_GMAIL"
export FLYBRAIN_MAIL_SUBJECT="$SUBJECT"
export FLYBRAIN_MAIL_BODY_PATH="$MAIL_BODY"
python3 - <<'PY'
import json, os, urllib.request

base = os.environ["AGENTMAIL_BASE_URL"].rstrip("/")
addr = os.environ["AGENTMAIL_ADDRESS"]
key = os.environ["AGENTMAIL_API_KEY"]
to = os.environ["FLYBRAIN_MAIL_TO"]
subject = os.environ["FLYBRAIN_MAIL_SUBJECT"]
body = open(os.environ["FLYBRAIN_MAIL_BODY_PATH"]).read()

payload = {"to": [to], "subject": subject, "text": body}
url = f"{base}/v0/inboxes/{addr}/messages/send"
req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode(),
    headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    },
    method="POST",
)
with urllib.request.urlopen(req, timeout=120) as resp:
    raw = resp.read().decode()
    print("AGENTMAIL_SENT", resp.status, raw[:800])
PY

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] cron fire done"
# trap removes cron on EXIT
