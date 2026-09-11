# Fly Cast

A small **connectome mouth**: activity through the published Drosophila larva wiring → text in → English out.

Same larval connectome lineage as [Fly Hero](https://github.com/actuallyrizzn/fly-hero). This library is the mouth; product-specific banks, cues, and demos live under `examples/`.

Layout mirrors [sanctumos/thalamus](https://github.com/sanctumos/thalamus): reusable core + forked examples.

## What this is

- A Python package (`flycast`) that runs sparse steps on the Winding 2023 larva connectome and learns a thin translator so words can come out.
- A **profile** system (`profile.toml`) so anyone can point the same core at a different cue vocabulary, reply bank, and lexicon.
- A flagship example — **Fly Hero / Clone Hero gameplay reactions** — under `examples/fly_hero/`.

Weird or dumb English is still a pass. Honesty tables (real wiring vs scrambled vs no-fly) stay mandatory for training claims.

## What this is not

- Not ChatGPT.
- Not insect cosplay / “we taught a fly English” without controls.
- Not a public Twitch bot by default (stream, accounts, and music policy are product choices — out of the core).

## Repository layout

```
fly-cast/
├── src/flycast/          # Core library (connectome, train, pick, guard, overlay, CLI)
├── examples/
│   └── fly_hero/         # Flagship product profile (Clone Hero / Fly Hero)
│       ├── profile.toml
│       ├── fixtures/     # reply bank, lexicon, recorded events
│       └── docs/         # our honesty / Level A–B notes
├── fixtures/             # Generic practice / TinyStories subset (no product cues)
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
flycast overlay serve   # http://127.0.0.1:8766/
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

Leave `src/flycast/` alone unless you are changing the shared mouth.

Events JSONL schema (generic):

```json
{"t": 1.0, "cue": "YOUR_CUE", "detail": "optional"}
```

## Chat / social plug-in shape

Profiles can declare cues like `CHAT` / `SOCIAL`. The same guard path applies (`flycast.external.reply_to_message`). Keep **`approve_mode=True`** for any public outbound post until a human turns that off for a named platform.

This repo does not register bot accounts or choose a stream host.

## Data

Larva connectome (Winding 2023) under `src/flycast/data/` — see that folder’s README.

## License

MIT. Connectome data is CC-BY (see `src/flycast/data/README.md`).
