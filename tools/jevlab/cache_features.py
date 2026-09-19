"""Write float16 features for one task, one arm at a time."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from flycast.jevlab.arms import arm_features, build_reservoir
from flycast.jevlab.cache import feature_path, parse_cfg, save_sidecar, skip_reason
from flycast.jevlab.data import load_split, stratified_indices
from flycast.jevlab.features import encode_packets
from flycast.jevlab.vectors import build_embed, load_glove
from flycast.tokenizer import Tokenizer

_CHUNK = 2000


def _data_root(root: Path, task: str) -> Path:
    if (root / "data" / task).is_dir():
        return root / "data"
    if (root / task).is_dir():
        return root
    raise FileNotFoundError(f"no split dir for {task} under {root}")


def _glove_file(root: Path) -> Path:
    manifest = root / "vectors" / "MANIFEST.json"
    if manifest.exists():
        name = json.loads(manifest.read_text(encoding="utf-8"))["file"]
        return root / "vectors" / name
    mini = root / "glove.mini.txt"
    if mini.exists():
        return mini
    raise FileNotFoundError(f"no GloVe manifest or glove.mini.txt under {root}")


def _ids(data_root: Path, task: str, split: str) -> list[str]:
    path = data_root / task / f"{split}.tsv"
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if line:
            ids.append(line.split("\t", 1)[0])
    return ids


def _split(data_root: Path, task: str, split: str) -> tuple[list[str], list[str], list[int]]:
    rows = load_split(task, split, root=data_root)
    ids = _ids(data_root, task, split)
    if len(ids) != len(rows):
        raise ValueError(f"{task} {split}: {len(ids)} ids, {len(rows)} rows")
    texts = [text for text, _label in rows]
    labels = [label for _text, label in rows]
    return ids, texts, labels


def _train_ids(cache_task: Path, ids: list[str], labels: list[int], cap: int) -> list[str]:
    path = cache_task / "train_cap_ids.json"
    take = min(cap, len(ids))
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if int(saved["n"]) == take:
            return list(saved["ids"])
        # Cap changed (e.g. timing run at 2000 then grid at 5000) — rewrite.
    chosen = stratified_indices(labels, take, 7)
    picked = [ids[int(i)] for i in chosen]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"seed": 7, "n": len(picked), "ids": picked}, indent=2) + "\n",
        encoding="utf-8",
    )
    return picked


def _apply_ids(
    ids: list[str], texts: list[str], labels: list[int], keep: list[str]
) -> tuple[list[str], list[str], list[int]]:
    index = {row_id: i for i, row_id in enumerate(ids)}
    missing = [row_id for row_id in keep if row_id not in index]
    if missing:
        raise ValueError(f"train cap ids missing from split: {missing[:3]}")
    picked = [index[row_id] for row_id in keep]
    return (
        [ids[i] for i in picked],
        [texts[i] for i in picked],
        [labels[i] for i in picked],
    )


def _width(arm: str, cfg, tok, embed: np.ndarray) -> int:
    if arm in {"nofly", "nofly_shuffled"}:
        base = cfg.inject_count
    else:
        reservoir = build_reservoir(cfg, tok, embed, scrambled=(arm == "scramble"))
        base = int(reservoir.n)
        del reservoir
    return base * 2 if cfg.pooling == "last+mean" else base


def _write_arm(
    *,
    root: Path,
    task: str,
    arm: str,
    cfg,
    split: str,
    texts: list[str],
    tok,
    embed: np.ndarray,
) -> None:
    cache = root / "cache"
    cfg_key = cfg.key()
    npy = feature_path(cache, task, arm, cfg_key, split)
    sidecar = npy.with_suffix(".json")
    reason = skip_reason(npy, sidecar, len(texts))
    if reason:
        print(f"{arm} {split} {reason}")
        return
    started = time.perf_counter()
    seqs, _fraction = encode_packets(tok, texts)
    width = _width(arm, cfg, tok, embed)
    npy.parent.mkdir(parents=True, exist_ok=True)
    mapped = np.lib.format.open_memmap(npy, mode="w+", dtype=np.float16, shape=(len(seqs), width))
    for start in range(0, len(seqs), _CHUNK):
        block = arm_features(arm, cfg, tok, embed, seqs[start : start + _CHUNK])
        mapped[start : start + len(block)] = block.astype(np.float16)
        del block
    mapped.flush()
    del mapped
    save_sidecar(
        sidecar,
        {
            "task": task,
            "arm": arm,
            "cfg_key": cfg_key,
            "split": split,
            "pooling": cfg.pooling,
            "n_rows": len(texts),
            "tokenizer_fingerprint": tok.fingerprint,
        },
    )
    seconds = time.perf_counter() - started
    mb = npy.stat().st_size / 1_000_000
    print(f"{arm} {split} rows={len(texts)} seconds={seconds:.2f} mb={mb:.2f}")


def run(args: argparse.Namespace) -> None:
    root = args.root.expanduser()
    cfg = parse_cfg(args.cfg)
    data_root = _data_root(root, args.task)
    cache_task = root / "cache" / args.task
    cache_task.mkdir(parents=True, exist_ok=True)
    train_ids, train_texts, _train_labels = _split(data_root, args.task, "train")
    tok_path = cache_task / "tokenizer.json"
    if tok_path.exists():
        tok = Tokenizer.load(tok_path)
        fresh = Tokenizer.build(train_texts, max_vocab=20000)
        if tok.fingerprint != fresh.fingerprint:
            raise ValueError("tokenizer fingerprint does not match a rebuild from train")
    else:
        tok = Tokenizer.build(train_texts, max_vocab=20000)
        tok.save(tok_path)
        reloaded = Tokenizer.load(tok_path, expect_fingerprint=tok.fingerprint)
        if reloaded.fingerprint != tok.fingerprint:
            raise ValueError("tokenizer fingerprint mismatch on reload")
    embed_path = cache_task / f"embed_i{cfg.inject_count}_seed{cfg.seed}.npy"
    if embed_path.exists():
        embed = np.load(embed_path)
    else:
        glove = load_glove(_glove_file(root), set(tok.id_to_token))
        embed, _coverage = build_embed(tok, glove, cfg.inject_count, cfg.seed)
        np.save(embed_path, embed)
    if embed.shape != (tok.size, cfg.inject_count):
        raise ValueError(f"embed {embed.shape} != ({tok.size}, {cfg.inject_count})")
    cap_ids = None
    if args.train_cap:
        _ids_all, _texts, labels = _split(data_root, args.task, "train")
        cap_ids = _train_ids(cache_task, train_ids, labels, args.train_cap)
    for arm in [part.strip() for part in args.arms.split(",") if part.strip()]:
        for split in [part.strip() for part in args.splits.split(",") if part.strip()]:
            ids, texts, labels = _split(data_root, args.task, split)
            if split == "train" and cap_ids is not None:
                ids, texts, labels = _apply_ids(ids, texts, labels, cap_ids)
            _write_arm(
                root=root,
                task=args.task,
                arm=arm,
                cfg=cfg,
                split=split,
                texts=texts,
                tok=tok,
                embed=embed,
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--arms", required=True)
    parser.add_argument("--cfg", required=True)
    parser.add_argument("--splits", required=True)
    parser.add_argument("--train-cap", type=int, default=0)
    parser.add_argument("--root", type=Path, required=True)
    run(parser.parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
