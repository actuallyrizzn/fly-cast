"""CLI for the two-stage validation grid. Never reads the test split."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from flycast.jevlab.arms import ArmCfg
from flycast.jevlab.cache import feature_path, parse_cfg
from flycast.jevlab.grid import PROTOCOL, cfg_grid, done_keys, rank_stage1, score_pooling_family
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
    from flycast.jevlab.state import write_desk

    if finished:
        write_desk(
            f"jevlab-grid-{task}",
            f"grid stage {stage} done",
            f"{done}/{total}",
            "best.json written",
            "await APPROVED before real run_task",
        )
        return
    step = f"{arm} {cfg_key}" if arm and cfg_key else "…"
    last = f"last {seconds:.0f}s" if seconds is not None else "in progress"
    write_desk(
        f"jevlab-grid-{task}",
        f"grid stage {stage} (valid only)",
        f"{done}/{total} · {step}",
        last,
        "no real test without APPROVED",
    )


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


def _family_key(arm: str, cfg: ArmCfg, seed: int) -> tuple:
    return (arm, cfg.leak, cfg.steps, cfg.radius, cfg.inject_count, cfg.input_scale, seed)


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
    done = sum(1 for arm, cfg, seed in points if (arm, cfg.key(), seed) in finished)
    state_dirs = [task_dir]
    if getattr(args, "watch_dir", None):
        watch = Path(args.watch_dir).expanduser()
        watch.mkdir(parents=True, exist_ok=True)
        state_dirs.append(watch)
    _write_desk_status(task=args.task, stage=stage, done=done, total=total)

    idx = 0
    while idx < len(points):
        arm, cfg, seed = points[idx]
        key = (arm, cfg.key(), seed)
        if key in finished:
            idx += 1
            continue
        # Group consecutive unfinished points that share the reservoir (pooling varies).
        family: list[ArmCfg] = []
        family_meta: list[tuple[str, ArmCfg, int]] = []
        j = idx
        gk = _family_key(arm, cfg, seed)
        while j < len(points):
            a2, c2, s2 = points[j]
            if _family_key(a2, c2, s2) != gk:
                break
            k2 = (a2, c2.key(), s2)
            if k2 not in finished:
                family.append(c2)
                family_meta.append((a2, c2, s2))
            j += 1
        if not family:
            idx = j
            continue
        lead = family_meta[0]
        _mirror_state(
            state_dirs,
            task=args.task,
            phase=f"grid-{stage}",
            now={
                "arm": lead[0],
                "seed": lead[2],
                "cfg_key": lead[1].key(),
                "step": f"fit ridge ×{len(family)} poolings",
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
            arm=lead[0],
            cfg_key=lead[1].key(),
        )
        rows = score_pooling_family(
            root=root,
            task=args.task,
            arm=lead[0],
            cfgs=family,
            seed=lead[2],
            train_cap=train_cap,
        )
        for row, (_a, c, _s) in zip(rows, family_meta):
            _append(jsonl, row)
            done += 1
            finished.add((_a, c.key(), _s))
            if stage == 1:
                _delete_cache(root, args.task, _a, c.key(), keep)
            valid = row.get("valid") or {}
            acc = float(valid.get("acc", 0.0))
            brier = float(valid.get("brier", 0.0))
            ece = float(valid.get("ece", 0.0))
            matrix = valid.get("confusion") or []
            labels = [str(i) for i in range(len(matrix))]
            _mirror_state(
                state_dirs,
                progress={"done": done, "total": total},
                now={
                    "arm": _a,
                    "seed": _s,
                    "cfg_key": c.key(),
                    "step": "done",
                    "started": None,
                    "elapsed_s": row["seconds"],
                },
                arms={
                    _a: {
                        "acc": [acc, acc, acc],
                        "brier": [brier, brier, brier],
                        "ece": [ece, ece, ece],
                        "seeds": 1,
                    }
                },
                confusion={"arm": _a, "labels": labels, "matrix": matrix},
                reliability={_a: valid.get("reliability") or []},
            )
            _write_desk_status(
                task=args.task,
                stage=stage,
                done=done,
                total=total,
                arm=_a,
                cfg_key=c.key(),
                seconds=float(row["seconds"]),
            )
        # Drop the shared last+mean cache unless a family member is kept.
        wide_key = ArmCfg(
            leak=lead[1].leak,
            steps=lead[1].steps,
            radius=lead[1].radius,
            inject_count=lead[1].inject_count,
            input_scale=lead[1].input_scale,
            pooling="last+mean",
            seed=lead[2],
        ).key()
        if stage == 1 and wide_key not in keep:
            _delete_cache(root, args.task, lead[0], wide_key, keep)
        idx = j

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
