# Architecture

Fly Cast is a **connectome mouth**: sparse activity on the published Drosophila larva wiring, plus a thin learned translator, so **text can come out**. It is not a general LLM wrapper and not Fly Hero’s hands.

```
events.jsonl ──► senses ──► prompt window ──► react (picker ± lexicon)
                                      │
                                      ▼
                                   guard ──► overlay state / stdout / (later) approve queue
```

## Layers

| Layer | Module(s) | Job |
|-------|-----------|-----|
| Connectome | `connectome`, `brain` | Load Winding larva graph; sparse `FlyBrain` steps; scramble / no-fly controls |
| Tokens | `tokenizer`, `generate`, `train` | Tiny vocab; Level A ridge readout; optional Level B embed+readout SGD |
| Product profile | `profile` | Cue vocabulary, bank/lexicon paths, what is “interesting” live |
| Prompt / bank | `prompt`, `bank`, `lexicon`, `picker`, `react` | Cue → prompt string → scored candidates (+ lexicon bonus) |
| Senses | `senses`, `replay`, `live` | Parse / follow `events.jsonl`; offline replay vs live follow |
| Safety | `guard`, `external` | Blocklist, URL strip, dedupe, rate limit, kill switch, approve_mode |
| Surface | `overlay`, `cli` | Local HTML overlay + `flycast` entry point |

## Events schema (generic)

Each line of the events file is JSON:

```json
{"t": 12.34, "cue": "MISS", "detail": "green"}
```

- `t` — event time (seconds). Used for HIT throttle and event-time dedupe.
- `cue` — uppercase token from the active profile’s vocabulary (or any string; unknown cues still prompt).
- `detail` — optional free text (lane color, chat snippet, etc.).

The **core never hard-codes Clone Hero**. Profiles decide which cues fire the mouth (`interesting` + optional `HIT` + detail match).

## Live default: picker, not free-write

Untrained / lightly trained free-write is weak on honesty gates. The live path scores a **reply bank** under the prompt (`mode=picked`). An optional **lexicon** adds soft weight so preferred mouth phrases win more often.

Free-write (`flycast say`, Level A/B generate) remains for research and honesty tables — not the product default.

## Honesty controls

Training claims must compare:

1. **Fly** — real wiring layout  
2. **Scramble** — same density, permuted partners  
3. **No-fly** — readout on recent embeds only  

If scramble or no-fly wins, say so. Do not claim “the wiring is why it talks” from a losing table. Flagship numbers: [`examples/fly_hero/docs/RESULTS.md`](../examples/fly_hero/docs/RESULTS.md).

## What stays out of core

Stream hosts, bot accounts, music policy, GPU Level C retuning of `W` magnitudes — product / ops choices. Core stays forkable without those.

## Related docs

- Profiles: [PROFILES.md](PROFILES.md)  
- CLI: [CLI.md](CLI.md)  
- Guard path: [SAFETY.md](SAFETY.md)
