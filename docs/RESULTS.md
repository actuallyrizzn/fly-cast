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
