# Fly Cast results

## Level A — TinyStories subset (CPU)

| | |
|--|--|
| Date | 2026-09-11 |
| Corpus | 40 TinyStories train rows (`fixtures/tinystories_subset.txt`), ~280 chars/line; **CDLA-Sharing-1.0** |
| Method | Frozen larva wiring, fixed random token embeds, dual ridge readout + logit gain; max 800 teacher-forced pairs |

| Control | CE loss (lower better) |
|---|---|
| Fly (real wiring) | 3.21 |
| Scramble | 3.02 |
| No-fly (last-K embeds) | 2.51 |

No-fly wins on this subset. Live path uses picker-first. Checkpoint: `checkpoints/level_a/` (local).

### Samples (fly, free-write)

> Once upon a time  
> , there was a night piece zigzag couldn't pretty thin middle? jug. head lily sat a box?. …

> The little girl  
> named their a tried fin relax now his soft. hurts hole " lay, don't one day, …

## Level B — embed + readout (W frozen)

| | |
|--|--|
| Date | 2026-09-11 |
| Method | Start from Level A ridge; SGD on embed + readout; wiring layout frozen |
| Held-out | `examples/fly_hero/fixtures/reaction_heldout.txt` |
| Train | `fixtures/tinystories_subset.txt` head |
| Script | `tools/compare_level_b.py` |

| Control | Held-out reaction CE |
|---|---|
| Level A fly | 6.29 |
| Level B fly | 7.66 |
| Scramble (A fit) | 6.33 |

B is +1.37 CE worse than A. Live default: **A + picker**.

### Samples

| | Missed it | Song starting |
|---|---|---|
| A | was shore. tiny max her rainbow… | hair toy was standing in the red… |
| B | was note a knee. she knew it was named beep. | always near the playing a time… |

## Reaction free-write climb (CPU)

| | |
|--|--|
| Date | 2026-09-11 |
| Train | `examples/fly_hero/fixtures/reaction_train.txt` (78 lines; bank + paraphrases) |
| Held-out | `examples/fly_hero/fixtures/reaction_heldout.txt` (10 lines; no exact leak) |
| Script | `tools/climb_reaction_freewrite.py` |
| Path doc | [FREEWRITE-CLIMB.md](FREEWRITE-CLIMB.md) |

### Level A honesty (reaction held-out CE)

| Control | CE (lower better) |
|---|---|
| Fly (A) | 3.36 |
| Scramble | 3.35 |
| No-fly | 3.59 |

Fly beats no-fly on reaction text (unlike TinyStories). Scramble ties fly within noise.

### Level B vs A

| Control | CE |
|---|---|
| Level A fly | 3.36 |
| Level B fly | 4.20 |
| Scramble (A) | 3.35 |

B is **+0.83 CE worse** than A (gate margin 0.05). **Gate: B_LOSES.** Level C stays parked. Live default stays **A + picker**.

### Samples

| Prompt | A | B |
|---|---|---|
| Missed it | green climbing. | . |
| Song starting | . | now. |
| Streak going | . | . |
| That's a wrap | . | for the chart done. |
| On time | . | . |

## License

This write-up: **CC-BY-SA-4.0**. TinyStories excerpt: **CDLA-Sharing-1.0**. [LICENSING.md](../../../LICENSING.md).
