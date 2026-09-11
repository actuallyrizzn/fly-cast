# CLI reference

Entry point: `flycast` (after `pip install -e .`).

Global flag (before the subcommand):

```text
flycast --profile PATH <command> ...
```

`PATH` may be a profile directory or a `profile.toml` file. Sets `FLYCAST_PROFILE` for that process.

## Commands

| Command | Purpose |
|---------|---------|
| `say PROMPT…` | Free-write continuation (research / weak until trained) |
| `overfit PATH` | Overfit a tiny practice file; prints fly vs scramble vs no-fly losses |
| `pick PROMPT CAND…` | Score candidates; print winner (`mode=picked`) |
| `replay EVENTS.jsonl` | Offline reactions from a recorded session |
| `guard TEXT…` | Run one line through the safety guard |
| `overlay set` | Write overlay state JSON |
| `overlay serve` | Serve local overlay HTML (default `127.0.0.1:8766`) |
| `live EVENTS.jsonl` | One-shot or `--follow` into overlay state |

### Common options

**replay / live**

- `--bank PATH` — override profile reply bank  
- `--guard` (replay) — enable guard  
- `--stop-path PATH` — kill-switch file (presence → silence)  
- `--line-log PATH` — append JSONL of guard decisions  
- `--state-path PATH` (live / overlay) — overlay state JSON  
- `--follow` / `--seconds N` (live) — tail the events file  

**say / pick / overfit**

- `--seed`, `--max-tokens`, `--epochs` as documented by `--help`

## Quick examples

```bash
flycast say "hello there"
flycast --profile examples/fly_hero replay examples/fly_hero/fixtures/events_midtempo.jsonl
flycast live examples/fly_hero/fixtures/events_midtempo.jsonl \
  --state-path /tmp/flycast-state.json --stop-path /tmp/flycast-STOP
flycast overlay serve --state-path /tmp/flycast-state.json
flycast guard "On time." --stop-path /tmp/flycast-STOP
```

See also [SAFETY.md](SAFETY.md) and [PROFILES.md](PROFILES.md).
