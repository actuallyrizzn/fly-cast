# Fly Cast

[![License: AGPL v3+](https://img.shields.io/badge/code-AGPL--3.0--or--later-blue.svg)](licenses/AGPL-3.0.txt)
[![Docs License: CC BY-SA 4.0](https://img.shields.io/badge/docs-CC%20BY--SA%204.0-lightgrey.svg)](licenses/CC-BY-SA-4.0.txt)

This is the mouth for the same larva connectome [Fly Hero](https://github.com/actuallyrizzn/fly-hero) uses for the hands. Text in. English out. Weird English still counts.

Domain stuff — cue lists, reply banks, lexicons — lives under `examples/`. The library itself does not care what game you’re playing.

## Docs

| Doc | |
|-----|--|
| [docs/README.md](docs/README.md) | Index |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the mouth runs |
| [docs/PROFILES.md](docs/PROFILES.md) | Fork a profile |
| [docs/CLI.md](docs/CLI.md) | Commands |
| [docs/SAFETY.md](docs/SAFETY.md) | Guard + kill switch |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | PRs |
| [LICENSING.md](LICENSING.md) | AGPL code / CC-BY-SA everything else |

## What you get

| Piece | Job |
|-------|-----|
| `flycast` package | Sparse steps on the Winding 2023 larva wiring + a thin translator so words come out |
| Profiles (`profile.toml`) | Your cues, bank, lexicon — swap the folder, keep the core |
| [`examples/fly_hero/`](examples/fly_hero/) | Flagship: Clone Hero / Fly Hero reactions |

Live default is the **picker** (bank + optional lexicon). Free-write exists for research. If you claim the wiring is why it talks, you owe the honesty table (fly vs scramble vs no-fly).

## What this is not

Not ChatGPT. Not “we taught a fly English.” Not a Twitch bot out of the box — stream host, accounts, and music policy are your call, not the library’s.

## Layout

| Path | What’s there |
|------|----------------|
| `src/flycast/` | Core (AGPL) |
| `examples/fly_hero/` | Flagship profile + fixtures + our results |
| `fixtures/` | Generic practice / TinyStories subset |
| `docs/` | Project docs (CC-BY-SA) |
| `licenses/` | Full AGPL + CC-BY-SA texts |
| `tests/` | Coverage gate ≥90% |

```mermaid
flowchart LR
  events["events.jsonl"] --> senses
  senses --> prompt["prompt window"]
  prompt --> react["picker ± lexicon"]
  react --> guard
  guard --> out["overlay / stdout / approve queue"]
```

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Try it

```bash
flycast say "hello there"
flycast replay examples/fly_hero/fixtures/events_midtempo.jsonl
flycast live examples/fly_hero/fixtures/events_midtempo.jsonl --state-path /tmp/flycast-state.json
flycast overlay serve --state-path /tmp/flycast-state.json
```

Overlay lands at `http://127.0.0.1:8766/`. Unset `FLYCAST_PROFILE` → flagship `examples/fly_hero`.

## Use it for something else

1. Copy `examples/fly_hero/` → `examples/your_thing/`
2. Edit `profile.toml`
3. Replace the bank (and lexicon if you want)
4. Point at it:

```bash
export FLYCAST_PROFILE=examples/your_thing
flycast replay path/to/events.jsonl
```

Or: `flycast --profile examples/your_thing replay path/to/events.jsonl`

Don’t touch `src/flycast/` unless you’re changing the shared mouth. Details: [docs/PROFILES.md](docs/PROFILES.md).

Events are one JSON object per line:

```json
{"t": 1.0, "cue": "YOUR_CUE", "detail": "optional"}
```

## Chat later

Same event file, same guard. `flycast.external.reply_to_message` never posts. Keep `approve_mode=True` until a human names a platform and turns that off. [docs/SAFETY.md](docs/SAFETY.md).

## Data

Larva connectome under `src/flycast/data/` — Winding 2023, **CC-BY** upstream. Same bytes Fly Hero ships. See that folder’s README.

## License

| Material | License |
|----------|---------|
| Code | [AGPL-3.0-or-later](licenses/AGPL-3.0.txt) |
| Docs and other non-code | [CC-BY-SA-4.0](licenses/CC-BY-SA-4.0.txt) |

Full map + third-party notices: [LICENSING.md](LICENSING.md). Connectome CSVs stay **CC-BY**; TinyStories subset stays **CDLA-Sharing-1.0**.
