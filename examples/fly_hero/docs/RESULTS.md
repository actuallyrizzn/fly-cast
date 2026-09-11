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

## License

This write-up: **CC-BY-SA-4.0**. TinyStories excerpt: **CDLA-Sharing-1.0**. [LICENSING.md](../../../LICENSING.md).
