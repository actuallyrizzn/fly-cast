# Architecture

Fly Cast runs activity through the published larva connectome and reads words out the other side. Hands stay in [Fly Hero](https://github.com/actuallyrizzn/fly-hero). This repo is the mouth.

```mermaid
flowchart LR
  events["events.jsonl"] --> senses
  senses --> prompt["prompt window"]
  prompt --> react["picker ± lexicon"]
  react --> guard
  guard --> overlay["overlay / stdout"]
  guard --> approve["approve queue"]
```

## Layers

| Layer | Module(s) | Job |
|-------|-----------|-----|
| Connectome | `connectome`, `brain` | Load Winding larva graph; sparse `FlyBrain` steps; scramble / no-fly controls |
| Tokens | `tokenizer`, `generate`, `train` | Tiny vocab; Level A ridge readout; optional Level B embed+readout SGD |
| Profile | `profile` | Cue vocab, bank/lexicon paths, what fires live |
| Prompt / bank | `prompt`, `bank`, `lexicon`, `picker`, `react` | Cue → prompt → scored candidates (+ lexicon bonus) |
| Senses | `senses`, `replay`, `live` | Parse / follow `events.jsonl` |
| Safety | `guard`, `external` | Blocklist, URL strip, dedupe, rate limit, kill switch, `approve_mode` |
| Surface | `overlay`, `cli` | Local HTML overlay + `flycast` CLI |

## Events

One JSON object per line:

```json
{"t": 12.34, "cue": "MISS", "detail": "green"}
```

| Field | Role |
|-------|------|
| `t` | Event time (seconds) — HIT throttle + event-time dedupe |
| `cue` | Token from the profile (unknown cues still prompt) |
| `detail` | Optional — lane, chat snippet, etc. |

The active profile sets which cues fire (`interesting`, plus optional `HIT` + detail match).

## Live default: picker

Live scores a **reply bank** under the prompt (`mode=picked`). Lexicon is a soft weight toward preferred phrases. `flycast say` and Level A/B generate are available for research and honesty runs.

## Honesty

Training reports include:

| Control | Meaning |
|---------|---------|
| Fly | Real wiring layout |
| Scramble | Same density, partners permuted |
| No-fly | Readout on recent embeds only |

Flagship numbers: [`examples/fly_hero/docs/RESULTS.md`](../examples/fly_hero/docs/RESULTS.md).

[Profiles](PROFILES.md) · [CLI](CLI.md) · [Safety](SAFETY.md)
