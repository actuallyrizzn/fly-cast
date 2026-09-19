# Jev-task lab journal — fly vs controls

- Generated: `2026-09-19T02:30:59Z`
- Protocol sha256: `8838fe8bec00a151a4c8b46b6ca5227ac80cac5cecae1dfe53efd3a4875361b7`
- Git: `54ea410`
- Protocol doc: [Doc #1392](https://tasks.decisionsciencecorp.com/admin/doc.php?id=1392)

## Runs

| run_dir | task | glass | c1 | c2 | c3 | pass | frames |
|---|---|---|---|---|---|---|---|
| `smoke-sst2-20260919-022242` | sst2 | True | False | True | True | False | 10 |

## Publishable

Internal record only. Not for external publication.

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


## Frames

(Upload scoring milestone frames from run cards; map in frame_uploads.json.)

<!-- hand:start -->
## What this does not prove

- Smoke bundles and unapproved runs are not publishable evidence.
- A pass on one task does not generalize to other tasks or to production Sanctum memory.
- Latency figures are ngram CPU medians, not hosted Jev comparisons by themselves.

## Process failures

1. 2026-09-18 — untrained readout probes were treated like tests; nuked. Protocol now requires APPROVED + trained heads.
2. Smoke bundle `smoke-sst2-20260919-022242` is glass plumbing only (400 training rows). Do not quote its accuracies.

## Reading the results

(Write one plain paragraph per task after that task's real run exists.)
<!-- hand:end -->
