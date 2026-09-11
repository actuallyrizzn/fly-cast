# Fly Cast

[![License: AGPL v3+](https://img.shields.io/badge/code-AGPL--3.0--or--later-blue.svg)](licenses/AGPL-3.0.txt)
[![Docs License: CC BY-SA 4.0](https://img.shields.io/badge/docs-CC%20BY--SA%204.0-lightgrey.svg)](licenses/CC-BY-SA-4.0.txt)

A small **connectome mouth**: activity through the published Drosophila larva wiring → text in → English out.

Same larval connectome lineage as [Fly Hero](https://github.com/actuallyrizzn/fly-hero). This library is the mouth; product-specific banks, cues, and demos live under `examples/`.

Layout mirrors [sanctumos/thalamus](https://github.com/sanctumos/thalamus): reusable core + forked examples.

## Documentation

| Start here | |
|------------|--|
| [docs/README.md](docs/README.md) | Doc index |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Pipeline and honesty controls |
| [docs/PROFILES.md](docs/PROFILES.md) | Forking with `profile.toml` |
| [docs/CLI.md](docs/CLI.md) | Command reference |
| [docs/SAFETY.md](docs/SAFETY.md) | Guard, kill switch, approve mode |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | How to contribute |
| [LICENSING.md](LICENSING.md) | Dual license + third-party notices |

## What this is

- A Python package (`flycast`) that runs sparse steps on the Winding 2023 larva connectome and learns a thin translator so words can come out.
- A **profile** system (`profile.toml`) so anyone can point the same core at a different cue vocabulary, reply bank, and lexicon.
- A flagship example — **Fly Hero / Clone Hero gameplay reactions** — under [`examples/fly_hero/`](examples/fly_hero/).

Weird or dumb English is still a pass. Honesty tables (real wiring vs scrambled vs no-fly) stay mandatory for training claims.

## What this is not

- Not ChatGPT.
- Not insect cosplay / “we taught a fly English” without controls.
- Not a public Twitch bot by default (stream, accounts, and music policy are product choices — out of the core).

## Repository layout

```
fly-cast/
├── src/flycast/              # Core library (AGPL)
├── examples/
│   └── fly_hero/             # Flagship product profile (CC-BY-SA content)
│       ├── profile.toml
│       ├── fixtures/
│       └── docs/RESULTS.md
├── fixtures/                 # Generic practice / TinyStories subset
├── docs/                     # Project documentation (CC-BY-SA)
├── licenses/                 # Full AGPL + CC-BY-SA texts
├── LICENSING.md
└── tests/
```

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Quick try (flagship example)

```bash
# Default profile is examples/fly_hero when FLYCAST_PROFILE is unset
flycast say "hello there"
flycast replay examples/fly_hero/fixtures/events_midtempo.jsonl
flycast live examples/fly_hero/fixtures/events_midtempo.jsonl --state-path /tmp/flycast-state.json
flycast overlay serve --state-path /tmp/flycast-state.json   # http://127.0.0.1:8766/
```

Untrained free-write is weak; **live default is the picker** from the profile’s reply bank (+ optional lexicon).

## Fork for your own domain

1. Copy `examples/fly_hero/` → `examples/your_thing/`.
2. Edit `profile.toml` (cue lists, interesting events, paths).
3. Replace `fixtures/reply_bank.tsv` and optionally `fixtures/fly_lexicon.tsv`.
4. Point the CLI at your profile:

```bash
export FLYCAST_PROFILE=examples/your_thing
# or: flycast --profile examples/your_thing replay path/to/events.jsonl
```

Details: [docs/PROFILES.md](docs/PROFILES.md). Leave `src/flycast/` alone unless you are changing the shared mouth.

Events JSONL schema (generic):

```json
{"t": 1.0, "cue": "YOUR_CUE", "detail": "optional"}
```

## Chat / social plug-in shape

Profiles can declare cues like `CHAT` / `SOCIAL`. The same guard path applies (`flycast.external.reply_to_message`). Keep **`approve_mode=True`** for any public outbound post until a human turns that off for a named platform. See [docs/SAFETY.md](docs/SAFETY.md).

This repo does not register bot accounts or choose a stream host.

## Data

Larva connectome (Winding 2023) under `src/flycast/data/` — **CC-BY** upstream; see that folder’s README. Same files Fly Hero ships.

## License

**Dual license** — see [LICENSING.md](LICENSING.md):

- **Code:** [AGPL-3.0-or-later](licenses/AGPL-3.0.txt)
- **Documentation and other non-code:** [CC-BY-SA-4.0](licenses/CC-BY-SA-4.0.txt)

Third-party: connectome CSVs remain **CC-BY** (Winding et al.); TinyStories subset remains **CDLA-Sharing-1.0**.
