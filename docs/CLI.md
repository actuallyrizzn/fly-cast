# CLI

After `pip install -e .`:

```bash
flycast --profile PATH <command> ...
```

`PATH` is a profile directory or a `profile.toml`. Sets `FLYCAST_PROFILE` for that run.

## Commands

| Command | Purpose |
|---------|---------|
| `say PROMPT…` | Free-write (research; weak until trained) |
| `overfit PATH` | Overfit a tiny practice file; fly vs scramble vs no-fly losses |
| `pick PROMPT CAND…` | Score candidates; print winner |
| `replay EVENTS.jsonl` | Offline reactions from a recorded session |
| `guard TEXT…` | One line through the safety guard |
| `overlay set` | Write overlay state JSON |
| `overlay serve` | Local overlay HTML (`127.0.0.1:8766`) |
| `live EVENTS.jsonl` | One-shot or `--follow` into overlay state |

## Options that matter

| Area | Flags |
|------|--------|
| replay / live | `--bank`, `--guard` (replay), `--stop-path`, `--line-log`, `--state-path`, `--follow`, `--seconds` |
| say / pick / overfit | `--seed`, `--max-tokens`, `--epochs` — see `--help` |

## Examples

```bash
flycast say "hello there"
flycast --profile examples/fly_hero replay examples/fly_hero/fixtures/events_midtempo.jsonl
flycast live examples/fly_hero/fixtures/events_midtempo.jsonl \
  --state-path /tmp/flycast-state.json --stop-path /tmp/flycast-STOP
flycast overlay serve --state-path /tmp/flycast-state.json
flycast guard "On time." --stop-path /tmp/flycast-STOP
```

[SAFETY.md](SAFETY.md) · [PROFILES.md](PROFILES.md)
