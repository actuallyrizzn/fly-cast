# tools/jevlab

Scripts for the Jev-task lab (fly vs scramble / no-fly / shuffled / TF-IDF).

| Script | What it does |
|---|---|
| `protocol.json` | Pre-registered grid, seeds, criteria, dataset pointers. Scorer reads this. |
| `fetch_sst2.py` | Freeze SST-2 train/valid/test plus the negation slice. |
| `fetch_clinc.py` | CLINC10 + CLINC150 splits and confusable slice. |
| `fetch_bugsev.py` | Bugzilla severity (MSR 2013) 3-level labels. |
| `fetch_glove.py` | GloVe 6B 100d download + check. |
| `make_smoke.py` | 500-row smoke fixtures + mini GloVe into `fixtures/jevlab/smoke/`. |
| `cache_features.py` | Float16 pooled features per (task, arm, cfg, split). |
| `grid.py` | Two-stage validation grid (never reads test). `--from` copies `best.json`. Writes `desk_status.txt`. |
| `run_task.py` | End-to-end bundle. Real data needs `APPROVED`; `--smoke` does not. |
| `score_run.py` | Pass/fail against `protocol.json` (CIs, publishable). |
| `journal_refresh.py` | Regenerate `docs/jevlab/JOURNAL.md` (+ optional Tasks publish). |
| `watch.sh` | Loopback HTTP + glass window on `DISPLAY=:0`. |
| `frames.sh` | Interval scrot / WebKit frames into the run bundle. |
| `snapshot_url.py` | WebKit snapshot of the watch URL (preferred over scrot). |
| `sync_run.sh` | Rsync run bundle off ngram (metrics, score, frames; not cache). |

Data and caches live on ngram under `~/fly-cast-runs/jevlab/`, not in the repo.
