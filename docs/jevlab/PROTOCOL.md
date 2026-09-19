# Jev-task protocol — fly vs controls (pre-registered)

**Status:** awaiting Mark's approval on task #4279. `run_task.py` will not score real data until `~/fly-cast-runs/jevlab/APPROVED` contains the sha256 below.

**protocol.json sha256:** `8838fe8bec00a151a4c8b46b6ca5227ac80cac5cecae1dfe53efd3a4875361b7`

Machine-readable copy: `tools/jevlab/protocol.json`. The scorer reads that file. Do not change criteria after run 1 starts. If a criterion turns out wrong, add a dated amendment section. Never edit the original.

## 1. Tasks and datasets

Tasks and datasets (see data card). Splits frozen with checksums. Test split never touched during tuning.

## 2. Controls

Controls, all with the same word vectors and the same readout recipe: scrambled wiring (degree-preserving), no-fly (mean-pooled vectors, no recurrence), order-shuffled input (same words, shuffled order), and a TF-IDF logistic reference so we know the ceiling.

## 3. Tuning grid

Tuning grid, run on validation only, same grid for fly and scramble: leak {0.3, 0.5, 0.8}, steps {1, 2, 4}, radius {0.7, 0.9, 1.1}, inject neurons {32, 64, 128}, input scale {0.5, 1, 2}, pooling {last, mean, last+mean}. Two-stage search (coarse seed 0 at 5k rows, fine top-10 at 20k rows x 3 seeds) — detail on #4303.

## 4. Seeds

Seeds: 5 per arm. Report mean and 95% CI.

## 5. Pass criteria

Pass criteria (per task): fly beats scramble with non-overlapping CIs; fly is at or above no-fly; fly loses more accuracy than no-fly when word order is shuffled (shows the recurrence is used). Calibration: Brier and reliability curve reported; temperature fitted on validation only.

## 6. Latency

Latency: ms per packet on the ngram CPU, measured on the test split, compared to the 70–500 ms hosted Jev figure.

## 7. Publish rule

Publish rule: external only if all pass criteria met on at least one task and the page reads cold. Otherwise internal digest.

What will not happen: paid inference (Lab 3 standing order), hosted Jev API, compaction corpus, Level C.

## 8. Datasets

| Task | URL | Licence | Test split | Row counts |
|---|---|---|---|---|
| sst2 | https://dl.fbaipublicfiles.com/glue/data/SST-2.zip | GLUE/SST-2, research use | GLUE dev.tsv (872 rows). Unlabeled GLUE test.tsv ignored. sha256 `c5d4733f9738b084e064836d98a27c7ddedc9bd3d8571a39fffb2d30eedd4005` | train 64349 / valid 3000 / test 872 / negation 184 |
| clinc150 | https://raw.githubusercontent.com/clinc/oos-eval/master/data/data_full.json | CC-BY-3.0 | their test + oos_test as `oos`. sha256 `a29710b72717f17a2514df8e9a5dfc5b37dbeb5ca1ee22f2b25fbd4a17918441` | train 15100 / valid 3100 / test 5500 |
| clinc10 | same file, 10 utility intents | CC-BY-3.0 | their test, restricted. sha256 `a229dfd59e5254930cc1053af12057ea00b5ce306666dac002562c759deb97fe` | train 1000 / valid 200 / test 300 / confusable 186 |
| bugsev | https://github.com/ansymo/msr2013-bug_dataset | No licence file. Cite Lamkanfi, Perez, Demeyer, MSR 2013. | stratified 10% after the 20000-row cap. sha256 `6715545ae7b01661bc1ff3bfafff476098061aedbd98832aeacf2972b9c023a6` | train 16000 / valid 2000 / test 2000. Before cap: low 9959, normal 110884, high 20606. Titles only (no description field). |
| glove | https://nlp.stanford.edu/data/glove.6B.zip | PDDL 1.0 | n/a (vectors). sha256 `95dde4dfd627ab26608d33e76d1195ec059734bd29089ea52cadb08d07c64544` | 400000 lines. SST-2 coverage 0.979 at inject 64 |

Row counts and test-split sha256 are filled by cards #4292–#4295. They are amendments to this table only, not to sections 1–7.

## 9. Grid

```json
{"leak":[0.3,0.5,0.8],"steps":[1,2,4],"radius":[0.7,0.9,1.1],"inject_count":[32,64,128],"input_scale":[0.5,1.0,2.0],"pooling":["last","mean","last+mean"]}
```

Seeds `[0,1,2,3,4]`. Ridge lambdas `[0.1,1,10,100]`. Temperature grid `[0.25,0.5,0.75,1,1.5,2,3,4,6,8]`.

### 9a. Two-stage search (disk and time)

729 points at full train size is too many for the laptop. The grid script runs:

1. **Stage 1 (coarse):** seed 0 only, train-cap 5000, all 729 points, ridge only, score = valid accuracy. Both fly and scramble.
2. **Stage 2 (fine):** top 10 points per arm from stage 1, train-cap 20000, seeds 0–2, ridge only, score = mean valid accuracy.
3. **Winner per arm** = best stage-2 mean. `nofly` reuses the fly winner's inject_count, pooling, and seed.

The test split is never read by the grid. Artifacts: `grid/<task>/stage1.jsonl`, `stage2.jsonl`, `best.json`.

## 10. Pass criteria as code

All three must hold on the test split for a task to pass. `publishable` = any task passes.

```
fly_mean_acc - 1.96*fly_sd/sqrt(5) > scr_mean_acc + 1.96*scr_sd/sqrt(5)
fly_mean_acc >= nofly_mean_acc
(fly_acc - fly_shuffled_acc) > (nofly_acc - nofly_shuffled_acc) + 0.01
```
