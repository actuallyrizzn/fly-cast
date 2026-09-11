# Fly Cast

Same larval fly-brain wiring as [Fly Hero](https://github.com/actuallyrizzn/fly-hero). This repo is the **mouth**: text in → English out. Fly Hero stays the hands that play Clone Hero.

## What this is

- A small program that runs activity through the published larva connectome and learns a thin translator so words can come out.
- Aimed at reacting to gameplay (hits, misses, streaks) and later chat/social — **as good as we can get**. Weird or dumb English is still a pass.
- Built and gated on the DSC Tasks board (Fly Hero → list **Fly Cast**). Feasibility: [Doc #1324](https://tasks.decisionsciencecorp.com/admin/doc.php?id=1324).

## What this is not

- Not ChatGPT.
- Not Sanctum Tectum / Broca.
- Not a public Twitch bot yet (stream, accounts, and music policy are deferred).
- Not “we taught a fly English” without an honesty table (real wiring vs scrambled vs no-fly).

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

On the ngram laptop: `~/fly-cast` (separate from `~/fly-hero`).

## Quick try

```bash
flycast say "hello there"
flycast replay fixtures/events_midtempo.jsonl
flycast live fixtures/events_midtempo.jsonl --state-path ~/fly-cast/overlay_state.json
flycast overlay serve   # http://127.0.0.1:8766/
```

Untrained free-write is weak; **live default is picker** from `fixtures/reply_bank.tsv`.

## How chat will plug in later

Gameplay already emits `CHAT` / `SOCIAL` cues into the same event file + guard path (`flycast.external.reply_to_message`). Fixture: `fixtures/chat_social.tsv`.

Later, a platform adapter (Twitch / Discord / something else — **Mark picks**) would:

1. Append `{cue: CHAT|SOCIAL, detail: message}` to the events JSONL (or call `reply_to_message` directly).
2. Run the reply through the **guard** (URLs stripped, blocklist, kill switch, line log).
3. Keep **`approve_mode=True`** for any public outbound post until Mark turns that off for a named platform.

This repo does **not** register bot accounts or choose a stream host.

## Data

Larva connectome (Winding 2023) under `src/flycast/data/` — see that folder’s README. Same files Fly Hero ships.

## License

MIT. Connectome data is CC-BY (see `src/flycast/data/README.md`).
