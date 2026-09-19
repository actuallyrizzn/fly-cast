"""CLI for the two-stage validation grid. Never reads the test split."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from flycast.jevlab.arms import ArmCfg
from flycast.jevlab.cache import feature_path, parse_cfg
from flycast.jevlab.grid import PROTOCOL, cfg_grid, done_keys, rank_stage1, score_point
from flycast.jevlab.state import write as write_state


def _append(jsonl: Path, row: dict) -> None:
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    with jsonl.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _mirror_state(dirs: list[Path], **kwargs) -> None:
    for path in dirs:
        write_state(path, **kwargs)


def _write_desk_status(
    *,
    task: str,
    stage: int,
    done: int,
    total: int,
    arm: str | None = None,
    cfg_key: str | None = None,
    seconds: float | None = None,
    finished: bool = False,
) -> None:
    """Rewrite desk_status.txt so the ngram desk window stays live (#4318)."""
    import os

    override = os.environ.get("JEVLAB_DESK_STATUS")
    desk = Path(override) if override else Path.home() / "fly-cast-runs" / "desk_status.txt"
    desk.parent.mkdir(parents=True, exist_ok=True)
    if finished:
        body = (
            f"jevlab-grid-{task}\n"
            f"grid stage {stage} done\n"
            f"{done}/{total}\n"
            f"best.json written\n"
            f"await APPROVED before real run_task\n"
        )
    else:
        step = f"{arm} {cfg_key}" if arm and cfg_key else "…"
        last = f"last {seconds:.0f}s" if seconds is not None else "in progress"
        body = (
            f"jevlab-grid-{task}\n"
            f"grid stage {stage} (valid only)\n"
            f"{done}/{total} · {step}\n"
            f"{last}\n"
            f"no real test without APPROVED\n"
        )
    desk.write_text(body, encoding="utf-8")


def _delete_cache(root: Path, task: str, arm: str, cfg_key: str, keep: set[str]) -> None:
    if cfg_key in keep:
        return
    for split in ("train", "valid"):
        path = feature_path(root / "cache", task, arm, cfg_key, split)
        for target in (path, path.with_suffix(".json")):
            if target.exists():
                target.unlink()


def _points_for_stage(stage: int, task_dir: Path, dry_run: bool) -> list[tuple[str, ArmCfg, int]]:
    arms = ("fly", "scramble")
    if dry_run:
        base = cfg_grid()[:2]
        points = []
        for arm in arms:
            for cfg in base:
                points.append((arm, cfg, 0))
        return points[:4]
    if stage == 1:
        return [(arm, cfg, 0) for arm in arms for cfg in cfg_grid()]
    points = []
    stage1 = task_dir / "stage1.jsonl"
    for arm in arms:
        for row in rank_stage1(stage1, arm, top=10):
            cfg = parse_cfg(row["cfg"])
            for seed in (0, 1, 2):
                cfg_seed = ArmCfg(
                    leak=cfg.leak,
                    steps=cfg.steps,
                    radius=cfg.radius,
                    inject_count=cfg.inject_count,
                    input_scale=cfg.input_scale,
                    pooling=cfg.pooling,
                    seed=seed,
                )
                points.append((arm, cfg_seed, seed))
    return points


def _write_best(task_dir: Path) -> None:
    stage2 = task_dir / "stage2.jsonl"
    winners: dict[str, dict] = {}
    for arm in ("fly", "scramble"):
        by_cfg: dict[str, list[float]] = {}
        if stage2.exists():
            for line in stage2.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if row["arm"] != arm:
                    continue
                # Strip seed from key for grouping — use cfg without seed change:
                # cfg already includes seed. Group by inject/pooling/leak/steps/radius/scale.
                base = row["cfg"].rsplit("_seed", 1)[0]
                by_cfg.setdefault(base, []).append(float(row["valid"]["acc"]))
        if not by_cfg and (task_dir / "stage1.jsonl").exists():
            # Stage 2 empty: fall back to stage 1 winner for dry-run paths.
            top = rank_stage1(task_dir / "stage1.jsonl", arm, top=1)
            if top:
                winners[arm] = {"cfg": top[0]["cfg"], "valid_acc": top[0]["valid"]["acc"]}
            continue
        ranked = sorted(
            ((cfg, float(sum(vals) / len(vals))) for cfg, vals in by_cfg.items()),
            key=lambda item: (-item[1], item[0]),
        )
        if ranked:
            cfg_base, acc = ranked[0]
            # Prefer seed 0 key if present in stage2, else reconstruct.
            winners[arm] = {"cfg": f"{cfg_base}_seed0", "valid_acc": acc}
    if "fly" in winners:
        fly = parse_cfg(winners["fly"]["cfg"])
        winners["nofly"] = {
            "cfg": ArmCfg(
                leak=fly.leak,
                steps=fly.steps,
                radius=fly.radius,
                inject_count=fly.inject_count,
                input_scale=fly.input_scale,
                pooling=fly.pooling,
                seed=fly.seed,
            ).key(),
            "note": "nofly reuses fly inject_count, pooling, and seed",
        }
    (task_dir / "best.json").write_text(json.dumps(winners, indent=2) + "\n", encoding="utf-8")


def copy_best_from(root: Path, task: str, from_task: str) -> int:
    """Reuse another task's grid winner (D2: clinc150 from clinc10). Skips stages."""
    src = root / "grid" / from_task / "best.json"
    if not src.is_file():
        print(f"missing source best.json: {src}", file=sys.stderr)
        return 5
    dest_dir = root / "grid" / task
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "best.json"
    payload = json.loads(src.read_text(encoding="utf-8"))
    payload["_copied_from"] = from_task
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"copied best.json {from_task} -> {task}")
    return 0


def run(args: argparse.Namespace) -> int:
    root = args.root.expanduser()
    if getattr(args, "from_task", None):
        return copy_best_from(root, args.task, args.from_task)
    if args.stage is None:
        print("--stage is required unless --from is set", file=sys.stderr)
        return 2
    task_dir = root / "grid" / args.task
    task_dir.mkdir(parents=True, exist_ok=True)
    stage = args.stage
    jsonl = task_dir / (f"stage{stage}.jsonl")
    train_cap = 5000 if stage == 1 else 20000
    if args.dry_run:
        train_cap = min(train_cap, 400)
    points = _points_for_stage(stage, task_dir, args.dry_run)
    finished = done_keys(jsonl) if args.resume else set()
    keep: set[str] = set()
    if stage == 2 and (task_dir / "stage1.jsonl").exists():
        for arm in ("fly", "scramble"):
            for row in rank_stage1(task_dir / "stage1.jsonl", arm, top=10):
                keep.add(row["cfg"])
    total = len(points)
    done = 0
    state_dirs = [task_dir]
    if getattr(args, "watch_dir", None):
        watch = Path(args.watch_dir).expanduser()
        watch.mkdir(parents=True, exist_ok=True)
        state_dirs.append(watch)
    _write_desk_status(task=args.task, stage=stage, done=done, total=total)
    for arm, cfg, seed in points:
        key = (arm, cfg.key(), seed)
        if key in finished:
            done += 1
            continue
        _mirror_state(
            state_dirs,
            task=args.task,
            phase=f"grid-{stage}",
            now={
                "arm": arm,
                "seed": seed,
                "cfg_key": cfg.key(),
                "step": "fit ridge",
                "started": None,
                "elapsed_s": 0,
            },
            progress={"done": done, "total": total},
        )
        _write_desk_status(
            task=args.task,
            stage=stage,
            done=done,
            total=total,
            arm=arm,
            cfg_key=cfg.key(),
        )
        row = score_point(
            root=root,
            task=args.task,
            arm=arm,
            cfg=cfg,
            seed=seed,
            train_cap=train_cap,
        )
        _append(jsonl, row)
        done += 1
        _mirror_state(
            state_dirs,
            progress={"done": done, "total": total},
            now={
                "arm": arm,
                "seed": seed,
                "cfg_key": cfg.key(),
                "step": "done",
                "started": None,
                "elapsed_s": row["seconds"],
            },
        )
        _write_desk_status(
            task=args.task,
            stage=stage,
            done=done,
            total=total,
            arm=arm,
            cfg_key=cfg.key(),
            seconds=float(row["seconds"]),
        )
        if stage == 1:
            _delete_cache(root, args.task, arm, cfg.key(), keep)
    if stage == 2 or args.dry_run:
        _write_best(task_dir)
    _mirror_state(
        state_dirs,
        phase="grid-done" if stage == 2 or args.dry_run else f"grid-{stage}",
    )
    _write_desk_status(
        task=args.task,
        stage=stage,
        done=done,
        total=total,
        finished=(stage == 2 or args.dry_run),
    )
    print(f"grid stage {stage} done={done}/{total}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument(
        "--stage",
        type=int,
        choices=(1, 2),
        default=None,
        help="1=coarse or 2=fine; required unless --from",
    )
    parser.add_argument(
        "--from",
        dest="from_task",
        default=None,
        help="Copy best.json from this task and skip the grid (e.g. clinc150 --from clinc10)",
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--watch-dir",
        type=Path,
        default=None,
        help="Also write state.json here for the glass watch page",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Shorthand: mirror state to <root>/runs/grid-watch",
    )
    args = parser.parse_args(argv)
    if args.watch and not args.watch_dir:
        args.watch_dir = Path(args.root).expanduser() / "runs" / "grid-watch"
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
