# Fly Hero mouth profile (product-specific)

This example wires **Fly Cast** (generic connectome → English mouth) to
[Fly Hero](https://github.com/actuallyrizzn/fly-hero) / Clone Hero gameplay.

If you are forking Fly Cast for your own domain, **copy this folder** and rename
it. Swap the fixtures, cue lists, and lexicon — leave `src/flycast/` alone.
Longer guide: [docs/PROFILES.md](../../docs/PROFILES.md).

## What lives here

| Path | Role |
|------|------|
| `profile.toml` | Cue vocabulary, interesting events, fixture paths |
| `fixtures/reply_bank.tsv` | Picker candidates per cue |
| `fixtures/fly_lexicon.tsv` | Weighted mouth-taste phrases |
| `fixtures/events_midtempo.jsonl` | Recorded Midtempo session for offline replay |
| `fixtures/chat_social.tsv` | Fake CHAT/SOCIAL lines (no platform accounts) |
| `docs/RESULTS.md` | Our Level A/B honesty numbers |

## Run (from repo root)

```bash
export FLYCAST_PROFILE=examples/fly_hero
flycast replay "$FLYCAST_PROFILE/fixtures/events_midtempo.jsonl"
flycast live "$FLYCAST_PROFILE/fixtures/events_midtempo.jsonl" --follow
flycast overlay serve
```

Default profile when unset is this directory (flagship example).

## Ops notes (ours)

- Laptop install: `~/fly-cast` beside `~/fly-hero`; share an events JSONL.
- Internal gating / feasibility lived on DSC Tasks (Fly Cast list); not required to use the code.
- Stream platform, bot accounts, and music policy are deliberately out of scope here.

## License

This example’s prose, TOML, banks, lexicon, and fixtures are **CC-BY-SA-4.0**.
The Fly Cast library code is **AGPL-3.0-or-later**. See [LICENSING.md](../../LICENSING.md).
