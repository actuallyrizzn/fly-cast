# Jev-task lab journal — fly vs controls

- Generated: `2026-09-20T08:21:31Z`
- Protocol sha256: `8838fe8bec00a151a4c8b46b6ca5227ac80cac5cecae1dfe53efd3a4875361b7`
- Git: `3273434`
- Protocol doc: [Doc #1392](https://tasks.decisionsciencecorp.com/admin/doc.php?id=1392)

## Runs

| run_dir | task | glass | c1 | c2 | c3 | pass | frames |
|---|---|---|---|---|---|---|---|
| `bugsev-20260920-075009` | bugsev | True | False | True | False | False | 22 |
| `clinc10-20260920-071929` | clinc10 | True | False | False | False | False | 12 |
| `clinc150-20260920-072543` | clinc150 | True | False | True | True | False | 29 |
| `smoke-sst2-20260919-022242` | sst2 | True | False | True | True | False | 10 |
| `sst2-20260920-060824` | sst2 | False | False | True | False | False | 57 |

## Publishable

Internal record only. Not for external publication.

### bugsev

Bundle `bugsev-20260920-075009`

| arm | acc mean [lo,hi] | brier | ece |
|---|---|---|---|
| fly | 0.784 [0.783,0.784] | 0.364 | 0.082 |
| scramble | 0.784 [0.783,0.784] | 0.365 | 0.083 |
| nofly | 0.784 [0.783,0.784] | 0.365 | 0.086 |
| fly_shuffled | 0.784 [0.783,0.785] | 0.364 | 0.081 |
| nofly_shuffled | 0.784 [0.783,0.785] | 0.364 | 0.086 |
| tfidf | 0.784 [0.784,0.784] | 0.346 | 0.012 |

Latency ms (median): fly=2.074114978313446 nofly=0.02793804742395878 tfidf=None

Shuffle drop: fly -0.001; nofly +0.000 (protocol wants fly drop larger by >0.01).

Fly test extras: top3_acc=1.000 off_by_one_acc=1.000


### clinc10

Bundle `clinc10-20260920-071929`

| arm | acc mean [lo,hi] | brier | ece |
|---|---|---|---|
| fly | 0.947 [0.941,0.953] | 0.165 | 0.258 |
| scramble | 0.955 [0.947,0.962] | 0.167 | 0.268 |
| nofly | 0.959 [0.957,0.960] | 0.197 | 0.311 |
| fly_shuffled | 0.951 [0.941,0.962] | 0.179 | 0.280 |
| nofly_shuffled | 0.949 [0.943,0.956] | 0.230 | 0.336 |
| tfidf | 0.977 [0.977,0.977] | 0.042 | 0.017 |

Latency ms (median): fly=4.825710551813245 nofly=0.027953414246439934 tfidf=None

Shuffle drop: fly -0.004; nofly +0.009 (protocol wants fly drop larger by >0.01).

Slices (mean over seeds):

| slice | arm | acc | top3 | off-by-one |
|---|---|---|---|---|
| test_confusable | fly | 0.949 | 0.984 | 0.962 |
| test_confusable | scramble | 0.958 | 0.987 | 0.968 |
| test_confusable | nofly | 0.966 | 0.978 | 0.971 |
| test_confusable | fly_shuffled | 0.944 | 0.986 | 0.956 |
| test_confusable | nofly_shuffled | 0.957 | 0.980 | 0.969 |

Fly test extras: top3_acc=0.981 off_by_one_acc=0.960


### clinc150

Bundle `clinc150-20260920-072543`

| arm | acc mean [lo,hi] | brier | ece |
|---|---|---|---|
| fly | 0.646 [0.643,0.649] | 0.954 | 0.617 |
| scramble | 0.646 [0.645,0.647] | 0.960 | 0.620 |
| nofly | 0.612 [0.611,0.612] | 0.977 | 0.595 |
| fly_shuffled | 0.631 [0.628,0.635] | 0.971 | 0.612 |
| nofly_shuffled | 0.627 [0.625,0.629] | 0.981 | 0.613 |
| tfidf | 0.776 [0.776,0.776] | 0.310 | 0.054 |

Latency ms (median): fly=5.4221139289438725 nofly=0.02743897493928671 tfidf=None

Shuffle drop: fly +0.015; nofly -0.015 (protocol wants fly drop larger by >0.01).

Fly test extras: top3_acc=0.756 off_by_one_acc=0.669


### sst2

Bundle `smoke-sst2-20260919-022242`

| arm | acc mean [lo,hi] | brier | ece |
|---|---|---|---|
| fly | 0.650 [0.552,0.748] | 0.459 | 0.133 |
| scramble | 0.610 [0.590,0.630] | 0.493 | 0.145 |
| nofly | 0.500 [0.500,0.500] | 0.505 | 0.050 |
| fly_shuffled | 0.610 [0.590,0.630] | 0.454 | 0.102 |
| nofly_shuffled | 0.500 [0.500,0.500] | 0.522 | 0.059 |
| tfidf | 0.600 [0.600,0.600] | 0.484 | 0.095 |

Latency ms (median): fly=37.385164527222514 nofly=0.03395002568140626 tfidf=None

Shuffle drop: fly +0.040; nofly +0.000 (protocol wants fly drop larger by >0.01).

Bundle `sst2-20260920-060824`

| arm | acc mean [lo,hi] | brier | ece |
|---|---|---|---|
| fly | 0.765 [0.760,0.770] | 0.324 | 0.050 |
| scramble | 0.763 [0.761,0.766] | 0.317 | 0.032 |
| nofly | 0.736 [0.735,0.737] | 0.343 | 0.059 |
| fly_shuffled | 0.764 [0.755,0.772] | 0.326 | 0.042 |
| nofly_shuffled | 0.741 [0.737,0.745] | 0.348 | 0.051 |
| tfidf | 0.818 [0.818,0.818] | 0.259 | 0.073 |

Latency ms (median): fly=2.495729480870068 nofly=0.027653994038701057 tfidf=None

Shuffle drop: fly +0.001; nofly -0.006 (protocol wants fly drop larger by >0.01).

Slices (mean over seeds):

| slice | arm | acc | top3 | off-by-one |
|---|---|---|---|---|
| test_negation | fly | 0.682 | 1.000 | 1.000 |
| test_negation | scramble | 0.673 | 1.000 | 1.000 |
| test_negation | nofly | 0.625 | 1.000 | 1.000 |
| test_negation | fly_shuffled | 0.657 | 1.000 | 1.000 |
| test_negation | nofly_shuffled | 0.634 | 1.000 | 1.000 |

Fly test extras: top3_acc=1.000 off_by_one_acc=1.000


## Frames

(Upload scoring milestone frames from run cards; map in frame_uploads.json.)

<!-- hand:start -->
## What this does not prove

- Smoke bundles and unapproved runs are not publishable evidence.
- A pass on one task does not generalize to other tasks or to production Sanctum memory.
- Latency figures are ngram CPU medians, not hosted Jev comparisons by themselves.
- None of the three real tasks passed the pre-registered c1∧c2∧c3 gate. Numbers below are an internal record only.

## Process failures

1. 2026-09-18 — untrained readout probes were treated like tests; nuked. Protocol now requires APPROVED + trained heads.
2. Smoke bundle `smoke-sst2-20260919-022242` is glass plumbing only (400 training rows). Do not quote its accuracies.
3. 2026-09-20 — D1 latency probe crashed after all seed metrics were written (`last+mean` dummy head width). Fixed in `3273434`; finished with `--score-only`.

## Reading the results

**sst2.** Fly lands at 76.5% test, a hair above scramble (76.3%) and clearly above no-fly (73.6%), but the scramble CI still overlaps so c1 fails. Negation helps fly vs no-fly (68% vs 62%) without clearing the gate. TF-IDF stays the reference at 81.8%. Order shuffle barely moves fly. Latency ~2.5 ms/packet on ngram.

**clinc10 / clinc150.** Keyword-heavy routing: no-fly and scramble match or beat fly on the 10-intent subset; full 150-class run has fly ≈ scramble (~64.6%) ahead of no-fly (~61%) with c2 and c3 true but c1 false. Confusable slice only exists for clinc10. TF-IDF dominates both.

**bugsev.** All arms collapse to ~78.4% (normal-heavy labels); off-by-one is trivially 1.0. No wiring signal. Passing here was always a bonus.
<!-- hand:end -->
