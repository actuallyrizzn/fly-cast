# Fly Cast results

## Level A — TinyStories subset (CPU)

- **Date:** 2026-09-11
- **Host:** Otto workstation (also runnable on NewDev / ngram)
- **Corpus:** 40 TinyStories train rows via HF datasets-server (`fixtures/tinystories_subset.txt`), truncated to ~280 chars/line. License: CDLA-Sharing-1.0.
- **Method:** frozen larva wiring, fixed random token embeds, dual ridge readout + logit gain. Max 800 teacher-forced pairs.

| Control | CE loss (lower better) |
|---|---|
| Fly (real wiring) | 3.21 |
| Scramble | 3.02 |
| No-fly (last-K embeds) | 2.51 |

On this small subset the no-fly control wins. That is an honesty finding, not a ship blocker — product continues; picker fallback is next. Do not claim “the wiring is why it talks” from these numbers.

### Samples (fly, free-write)

> Once upon a time  
> , there was a night piece zigzag couldn't pretty thin middle? jug. head lily sat a box?. …

> The little girl  
> named their a tried fin relax now his soft. hurts hole " lay, don't one day, …

Weird/broken English — expected at Level A on a tiny CPU subset. Otto QA gate #3738: English-shaped enough to keep climbing (picker-first for gameplay).

Checkpoint: `checkpoints/level_a/` (local; not in git).

## Level B — train input embeds + readout (W frozen)

- **Date:** 2026-09-11
- **Method:** start from Level A ridge readout; SGD on embed + readout (wiring layout frozen). Held-out: `examples/fly_hero/fixtures/reaction_heldout.txt`. Train: `fixtures/tinystories_subset.txt` head. Script: `tools/compare_level_b.py`.

| Control | Held-out reaction CE |
|---|---|
| Level A fly | 6.29 |
| Level B fly | 7.66 |
| Scramble (A fit) | 6.33 |

**B did not beat A** (+1.37 CE worse). Gate #3752: **stay on A + picker** as live default; B experimental only. **Do not open Level C.**

### Samples

| | Missed it | Song starting |
|---|---|---|
| A | was shore. tiny max her rainbow… | hair toy was standing in the red… |
| B | was note a knee. she knew it was named beep. | always near the playing a time… |
