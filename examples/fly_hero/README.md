# Fly Hero mouth profile

Wires Fly Cast to [Fly Hero](https://github.com/actuallyrizzn/fly-hero) / Clone Hero. Fork the folder for a different domain; leave `src/flycast/` alone. Guide: [docs/PROFILES.md](../../docs/PROFILES.md).

## Contents

| Path | Role |
|------|------|
| `profile.toml` | Cues, interesting events, fixture paths |
| `fixtures/reply_bank.tsv` | Picker candidates per cue |
| `fixtures/fly_lexicon.tsv` | Weighted mouth phrases |
| `fixtures/events_midtempo.jsonl` | Midtempo session for offline replay |
| `fixtures/chat_social.tsv` | Fake CHAT/SOCIAL lines (no accounts) |
| `docs/RESULTS.md` | Level A/B honesty numbers |

## Run

```bash
export FLYCAST_PROFILE=examples/fly_hero
flycast replay "$FLYCAST_PROFILE/fixtures/events_midtempo.jsonl"
flycast live "$FLYCAST_PROFILE/fixtures/events_midtempo.jsonl" --follow
flycast overlay serve
```

Unset profile → this directory is the default.

## Ops (our box)

| Detail | |
|--------|--|
| Laptop paths | `~/fly-cast` next to `~/fly-hero`; shared events JSONL |
| Stream / bots / music | Out of scope here |

## License

Prose, TOML, banks, lexicon, fixtures: **CC-BY-SA-4.0**. Library: **AGPL-3.0-or-later**. [LICENSING.md](../../LICENSING.md).
