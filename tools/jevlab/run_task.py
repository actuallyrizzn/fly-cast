"""One command for a task end to end. Real data needs APPROVED; --smoke does not."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from flycast.jevlab.arms import ArmCfg
from flycast.jevlab.cache import feature_path, parse_cfg
from flycast.jevlab.data import load_split
from flycast.jevlab.latency import nofly_latency_ms, packet_latency_ms
from flycast.jevlab.readout import fit_ridge_classes, metrics, predict_proba
from flycast.jevlab.reference import tfidf_reference
from flycast.jevlab.scorer import evaluate, publishable
from flycast.jevlab.state import frame, write as write_state, write_desk
from flycast.tokenizer import Tokenizer

ARMS = ("fly", "scramble", "nofly", "fly_shuffled", "nofly_shuffled")
PROTOCOL_PATH = Path(__file__).resolve().parents[2] / "tools" / "jevlab" / "protocol.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_sha(repo: Path) -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True)
            .strip()
        )
    except Exception:
        return "unknown"


def _data_root(root: Path, task: str) -> Path:
    if (root / "data" / task).is_dir():
        return root / "data"
    return root


def _labels(root: Path, task: str, split: str) -> np.ndarray:
    data = _data_root(root, task)
    tsv = data / task / f"{split}.tsv"
    labels = []
    for line in tsv.read_text(encoding="utf-8").splitlines()[1:]:
        if line:
            labels.append(int(line.split("\t")[2]))
    return np.asarray(labels, dtype=np.int64)


def _slice_files(data: Path, task: str) -> list[str]:
    found = []
    for path in sorted((data / task).glob("test_*.tsv")):
        found.append(path.stem)
    return found


def _fit_and_score(
    root: Path,
    task: str,
    arm: str,
    cfg: ArmCfg,
    run_dir: Path,
    seed: int,
) -> None:
    from tools.jevlab.cache_features import main as cache_main

    data = _data_root(root, task)
    slices = _slice_files(data, task)
    split_names = ["train", "valid", "test", *slices]
    cache_main(
        [
            "--task",
            task,
            "--arms",
            arm,
            "--cfg",
            json.dumps(
                {
                    "leak": cfg.leak,
                    "steps": cfg.steps,
                    "radius": cfg.radius,
                    "inject_count": cfg.inject_count,
                    "input_scale": cfg.input_scale,
                    "pooling": cfg.pooling,
                    "seed": seed,
                }
            ),
            "--splits",
            ",".join(split_names),
            "--root",
            str(root),
        ]
    )
    x_train = np.load(feature_path(root / "cache", task, arm, cfg.key(), "train")).astype(np.float32)
    x_valid = np.load(feature_path(root / "cache", task, arm, cfg.key(), "valid")).astype(np.float32)
    x_test = np.load(feature_path(root / "cache", task, arm, cfg.key(), "test")).astype(np.float32)
    y_train = _labels(root, task, "train")
    y_valid = _labels(root, task, "valid")
    y_test = _labels(root, task, "test")
    # train may be capped — match feature rows via train_cap_ids if present.
    cap = root / "cache" / task / "train_cap_ids.json"
    if cap.exists() and len(y_train) != len(x_train):
        by_id = {}
        for line in (data / task / "train.tsv").read_text(encoding="utf-8").splitlines()[1:]:
            if line:
                row_id, _text, label = line.split("\t")
                by_id[row_id] = int(label)
        order = json.loads(cap.read_text(encoding="utf-8"))["ids"]
        y_train = np.asarray([by_id[i] for i in order], dtype=np.int64)
    n_classes = int(max(int(y_train.max()), int(y_valid.max()), int(y_test.max())) + 1)
    head, _info = fit_ridge_classes(x_train, y_train, n_classes, x_valid=x_valid, y_valid=y_valid)
    metrics_dir = run_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    proba_dir = run_dir / "proba"
    proba_dir.mkdir(parents=True, exist_ok=True)

    def _write_split(split: str, x: np.ndarray, y: np.ndarray, *, save_proba: bool) -> None:
        proba = predict_proba(head, x)
        payload = metrics(proba, y)
        payload.update({"task": task, "arm": arm, "seed": seed, "split": split})
        (metrics_dir / f"{arm}_seed{seed}_{split}.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        if save_proba:
            np.save(proba_dir / f"{arm}_seed{seed}_{split}.npy", proba.astype(np.float32))

    _write_split("valid", x_valid, y_valid, save_proba=False)
    _write_split("test", x_test, y_test, save_proba=True)
    for slice_name in slices:
        x_slice = np.load(
            feature_path(root / "cache", task, arm, cfg.key(), slice_name)
        ).astype(np.float32)
        y_slice = _labels(root, task, slice_name)
        _write_split(slice_name, x_slice, y_slice, save_proba=True)


def run(args: argparse.Namespace) -> int:
    repo = Path(__file__).resolve().parents[2]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    root = args.root.expanduser()
    protocol = Path(args.protocol).expanduser() if args.protocol else PROTOCOL_PATH
    digest = _sha256(protocol)
    if not args.smoke:
        approved = root / "APPROVED"
        if not approved.exists() or approved.read_text(encoding="utf-8").strip() != digest:
            print("missing or mismatched APPROVED", file=sys.stderr)
            return 4
    else:
        smoke = Path(__file__).resolve().parents[2] / "fixtures" / "jevlab" / "smoke"
        if not (root / "data").exists():
            # Caller may already have laid out a smoke root.
            pass
    best_path = root / "grid" / args.task / "best.json"
    if not best_path.exists():
        print("missing grid best.json — run the grid first", file=sys.stderr)
        return 5
    best = json.loads(best_path.read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.out).expanduser() if args.out else root / "runs" / f"{args.task}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"run_dir {run_dir}")
    (run_dir / "protocol.json").write_bytes(protocol.read_bytes())
    (run_dir / "protocol.sha256").write_text(digest + "\n", encoding="utf-8")
    seeds = args.seeds if args.seeds is not None else json.loads(protocol.read_text())["seeds"]
    if isinstance(seeds, str):
        seeds = [int(part) for part in seeds.split(",") if part.strip()]
    tok_path = root / "cache" / args.task / "tokenizer.json"
    fingerprint = Tokenizer.load(tok_path).fingerprint if tok_path.exists() else ""
    config = {
        "task": args.task,
        "best": best,
        "seeds": seeds,
        "tokenizer_fingerprint": fingerprint,
        "git_sha": _git_sha(repo),
        "smoke": bool(args.smoke),
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    watch_proc = None
    frames_proc = None
    if args.watch:
        write_state(run_dir, task=args.task, phase="watch-start")
        watch_proc = subprocess.Popen(
            ["bash", str(repo / "tools" / "jevlab" / "watch.sh"), str(run_dir)],
            stdout=open(run_dir / "watch.log", "w"),
            stderr=subprocess.STDOUT,
        )
        # Wait until the page is actually serving (not just PID written).
        ready = False
        for _ in range(80):
            url_path = run_dir / "watch" / "URL"
            if url_path.exists():
                url = url_path.read_text(encoding="utf-8").strip()
                try:
                    import urllib.request

                    with urllib.request.urlopen(url, timeout=1) as resp:
                        if resp.status == 200:
                            ready = True
                            break
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(0.25)
        if not ready:
            print("watch URL never became ready", file=sys.stderr)
        if args.frames:
            frames_proc = subprocess.Popen(
                [
                    "bash",
                    str(repo / "tools" / "jevlab" / "frames.sh"),
                    str(run_dir),
                    str(int(args.frames)),
                ],
                stdout=open(run_dir / "frames.log", "w"),
                stderr=subprocess.STDOUT,
            )

    (run_dir / "grid_done").write_text("ok\n", encoding="utf-8")
    write_state(run_dir, task=args.task, phase="grid-done")
    frame(run_dir, "grid_done")

    fly_cfg = parse_cfg(best["fly"]["cfg"])
    scr_cfg = parse_cfg(best["scramble"]["cfg"])
    nofly_cfg = parse_cfg(best.get("nofly", best["fly"])["cfg"])
    arm_cfg = {
        "fly": fly_cfg,
        "scramble": scr_cfg,
        "nofly": nofly_cfg,
        "fly_shuffled": fly_cfg,
        "nofly_shuffled": nofly_cfg,
    }
    started = datetime.now(timezone.utc)
    try:
        for seed in seeds:
            for arm in ARMS:
                cfg = ArmCfg(
                    leak=arm_cfg[arm].leak,
                    steps=arm_cfg[arm].steps,
                    radius=arm_cfg[arm].radius,
                    inject_count=arm_cfg[arm].inject_count,
                    input_scale=arm_cfg[arm].input_scale,
                    pooling=arm_cfg[arm].pooling,
                    seed=seed,
                )
                write_state(
                    run_dir,
                    task=args.task,
                    phase="seeds",
                    now={"arm": arm, "seed": seed, "cfg_key": cfg.key(), "step": "fit ridge"},
                )
                write_desk(
                    f"jevlab-run-{args.task}",
                    f"seed {seed} · {arm}",
                    f"fitting ridge",
                    cfg.key(),
                    "no real test without APPROVED" if not args.smoke else "smoke",
                )
                print(f"arm {arm} seed {seed}")
                _fit_and_score(root, args.task, arm, cfg, run_dir, seed)
            # TF-IDF once per seed
            data = _data_root(root, args.task)
            train = load_split(args.task, "train", root=data)
            valid = load_split(args.task, "valid", root=data)
            test = load_split(args.task, "test", root=data)
            ref = tfidf_reference(
                [t for t, _ in train],
                [y for _, y in train],
                [t for t, _ in valid],
                [y for _, y in valid],
                [t for t, _ in test],
                [y for _, y in test],
                seed=seed,
            )
            for split in ("valid", "test"):
                payload = dict(ref[split])
                payload.update({"task": args.task, "arm": "tfidf", "seed": seed, "split": split})
                (run_dir / "metrics" / f"tfidf_seed{seed}_{split}.json").write_text(
                    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
                )
            print(f"arm tfidf seed {seed}")
            frame(run_dir, f"seed{seed}")
        # Latency on winner
        write_state(run_dir, phase="latency")
        texts = [text for text, _ in load_split(args.task, "train", root=_data_root(root, args.task))][:200]
        tok = Tokenizer.load(root / "cache" / args.task / "tokenizer.json")
        embed = np.load(
            root / "cache" / args.task / f"embed_i{fly_cfg.inject_count}_seed{fly_cfg.seed}.npy"
        )
        from flycast.jevlab.arms import build_reservoir
        from flycast.jevlab.readout import Head

        res = build_reservoir(fly_cfg, tok, embed, scrambled=False)
        head = Head(
            w=np.zeros((res.n, 2), np.float32),
            b=np.zeros(2, np.float32),
            temperature=1.0,
            kind="ridge",
            lam=1.0,
            mu=np.zeros(res.n, np.float32),
            sd=np.ones(res.n, np.float32),
        )
        fly_lat = packet_latency_ms(
            tok, res, head, texts, pooling=fly_cfg.pooling, n=min(50, len(texts)), seed=0
        )
        nofly_lat = nofly_latency_ms(
            tok, embed, texts, pooling=nofly_cfg.pooling, n=min(50, len(texts)), seed=0
        )
        latency = {
            "fly": fly_lat["median_ms"],
            "nofly": nofly_lat["median_ms"],
            "tfidf": None,
            "fly_detail": fly_lat,
            "nofly_detail": nofly_lat,
        }
        (run_dir / "latency.json").write_text(json.dumps(latency, indent=2) + "\n", encoding="utf-8")
        write_state(run_dir, phase="scoring", latency_ms=latency)
        frame(run_dir, "latency")
        write_desk(
            f"jevlab-run-{args.task}",
            "scoring",
            "evaluating criteria",
            "",
            "smoke" if args.smoke else "real",
        )
        result = evaluate(run_dir, protocol)
        result["publishable"] = publishable([result])
        (run_dir / "score.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        for arm, pack in result["arms"].items():
            mean, lo, hi = pack["acc"]
            print(f"{arm} | {mean:.3f} [{lo:.3f}, {hi:.3f}] | {pack['brier'][0]:.3f} | {pack['ece'][0]:.3f}")
        write_state(
            run_dir,
            phase="done",
            criteria=result["criteria"],
            **{"pass": result["pass"]},
        )
        write_desk(
            f"jevlab-run-{args.task}",
            "done",
            f"pass={result['pass']} publishable={result['publishable']}",
            str(run_dir.name),
            "smoke" if args.smoke else "real",
        )
        frame(run_dir, "scoring")
        finished = datetime.now(timezone.utc)
        index = root / "runs" / "INDEX.tsv"
        index.parent.mkdir(parents=True, exist_ok=True)
        if not index.exists():
            index.write_text(
                "run_dir\ttask\tpass\tpublishable\tstarted\tfinished\n", encoding="utf-8"
            )
        with index.open("a", encoding="utf-8") as handle:
            handle.write(
                f"{run_dir}\t{args.task}\t{result['pass']}\t{result['publishable']}\t"
                f"{started.isoformat()}\t{finished.isoformat()}\n"
            )
        print(f"pass={result['pass']} publishable={result['publishable']}")
        if not args.smoke:
            sync = repo / "tools" / "jevlab" / "sync_run.sh"
            if sync.exists():
                subprocess.run(["bash", str(sync), str(run_dir)], check=False)
        return 0
    finally:
        # Stop interval frames first, then the watch page.
        pid_file = run_dir / "watch" / "PID"
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text().strip()), 15)
            except OSError:
                pass
        if frames_proc is not None:
            frames_proc.terminate()
            frames_proc.wait(timeout=10)
        if watch_proc is not None:
            watch_proc.terminate()
            try:
                watch_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                watch_proc.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--protocol", type=Path, default=None)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--seeds", default=None)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--frames", type=int, default=0, help="interval seconds; 0 = off")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
