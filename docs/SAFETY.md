# Safety

Every outbound mouth line is meant to pass through **`flycast.guard.Guard`** before overlay, stdout (when guarded), or a future public post path.

## What the guard does

| Check | Behavior |
|-------|----------|
| Kill switch | If `stop_path` exists as a file → deny (`kill_switch`) |
| Blocklist | Conservative seed phrases (self-harm, sexual, slurs); expandable |
| URL strip | Removes `http(s)://`, `www.`, `mailto:` spans from allowed lines |
| Length | Caps line length |
| Dedupe | TTL on identical lines; live path prefers **event time** over wall clock |
| Rate limit | Caps how often lines may pass |
| Line log | Optional JSONL of decisions (`allowed`, `reason`, `cues`, `destination`, …) |

Denied lines become **silent** on the overlay (`mode=silent`) with a reason in logs / replay output.

## Kill switch

```bash
touch ~/fly-cast/STOP          # silence
rm -f ~/fly-cast/STOP          # resume
```

CLI: `--stop-path` on `replay`, `live`, and `guard`.

## Chat / social

`flycast.external.reply_to_message` builds a bank reply and runs the guard. It **never** posts to a platform.

- Keep **`approve_mode=True`** for any public outbound until a human turns that off for a **named** platform.
- Destination in the log is `approve-queue` when approve mode is on.

Fixture-only chat lines live under the profile (e.g. `examples/fly_hero/fixtures/chat_social.tsv`). This repo does not register bot accounts.

## HIT throttle (live)

Live follow throttles `HIT` reactions (~5s event-time spacing by default) so strum spam does not flood the overlay. Profile `interesting` cues still fire normally.

## What this is not

- Not a complete moderation product.
- Not permission to skip the guard on stream.
- Not a substitute for platform ToS or music policy decisions.
