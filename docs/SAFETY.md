# Safety

Outbound lines go through **`flycast.guard.Guard`** before overlay, guarded stdout, or an approve queue.

```mermaid
flowchart LR
  line["candidate line"] --> kill{"STOP file?"}
  kill -->|yes| silent["silent"]
  kill -->|no| checks["blocklist / URL / length / dedupe / rate"]
  checks -->|fail| silent
  checks -->|pass| out["overlay / log / approve queue"]
```

## Checks

| Check | Behavior |
|-------|----------|
| Kill switch | `stop_path` exists → deny (`kill_switch`) |
| Blocklist | Seed phrases (self-harm, sexual, slurs); expandable |
| URL strip | Drops `http(s)://`, `www.`, `mailto:` spans on allowed lines |
| Length | Caps line length |
| Dedupe | TTL on identical lines; live prefers **event time** |
| Rate limit | Caps how often lines pass |
| Line log | Optional JSONL (`allowed`, `reason`, `cues`, `destination`, …) |

Denied → overlay `mode=silent`, reason in the log / replay line.

## Kill switch

```bash
touch ~/fly-cast/STOP
rm -f ~/fly-cast/STOP
```

`--stop-path` on `replay`, `live`, and `guard`.

## Chat / social

`reply_to_message` picks a bank reply and runs the guard. Public outbound uses `approve_mode` and a platform adapter you wire separately.

| Setting | Effect |
|---------|--------|
| `approve_mode=True` | Log destination `approve-queue`; human gate before post |
| Fixture lines | e.g. `examples/fly_hero/fixtures/chat_social.tsv` |

## HIT throttle

Live follow spaces `HIT` reactions (~5s event time by default). Profile `interesting` cues still fire on their own schedule.
