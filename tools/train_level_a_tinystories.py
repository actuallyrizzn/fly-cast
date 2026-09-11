"""Download a TinyStories text subset and train Level A (ridge readout)."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from flycast.brain import build_fly_brain, build_no_fly
from flycast.generate import generate
from flycast.tokenizer import Tokenizer
from flycast.train import train_fly_level_a, train_no_fly

# Small public sample mirrors / raw story dumps are flaky; we ship a bootstrap
# corpus builder that pulls the HF dataset scriptlessly via the datasets server
# rows API (no torch required for download).
HF_ROWS = (
    "https://datasets-server.huggingface.co/rows"
    "?dataset=roneneldan%2FTinyStories&config=default&split=train"
)


def fetch_lines(*, limit: int, offset: int = 0) -> list[str]:
    lines: list[str] = []
    page = 100
    while len(lines) < limit:
        need = min(page, limit - len(lines))
        url = f"{HF_ROWS}&offset={offset + len(lines)}&length={need}"
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        rows = data.get("rows") or []
        if not rows:
            break
        for row in rows:
            text = (row.get("row") or {}).get("text") or ""
            text = " ".join(text.strip().split())
            if text:
                # keep short-ish lines for CPU ridge
                if len(text) > 280:
                    text = text[:280].rsplit(" ", 1)[0]
                lines.append(text)
        if len(rows) < need:
            break
    return lines[:limit]


def save_checkpoint(
    path: Path,
    *,
    tokenizer: Tokenizer,
    brain,
    meta: dict,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    tokenizer.save(path / "tokenizer.json")
    import numpy as np

    np.savez_compressed(
        path / "brain.npz",
        syn_pre=brain.syn_pre,
        syn_post=brain.syn_post,
        syn_val=brain.syn_val,
        inject=brain.inject,
        embed=brain.embed,
        readout=brain.readout,
        logit_bias=getattr(brain, "_logit_bias", np.zeros(brain.vocab_size, dtype=np.float32)),
        n_neurons=np.array([brain.n_neurons]),
        leak=np.array([brain.leak]),
        steps=np.array([brain.steps]),
        input_scale=np.array([brain.input_scale]),
    )
    (path / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200, help="Number of TinyStories rows")
    parser.add_argument("--out", type=Path, default=Path("checkpoints/level_a"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--corpus", type=Path, default=Path("fixtures/tinystories_subset.txt"))
    parser.add_argument("--samples", type=int, default=10)
    args = parser.parse_args()

    if args.corpus.is_file() and sum(1 for _ in args.corpus.open()) >= max(20, args.limit // 2):
        lines = [ln.strip() for ln in args.corpus.read_text().splitlines() if ln.strip()]
        lines = lines[: args.limit]
        print(f"loaded corpus {args.corpus} lines={len(lines)}")
    else:
        print(f"fetching TinyStories rows limit={args.limit}")
        lines = fetch_lines(limit=args.limit)
        args.corpus.parent.mkdir(parents=True, exist_ok=True)
        args.corpus.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {args.corpus} lines={len(lines)}")

    tokenizer = Tokenizer.build(lines, max_vocab=4000)
    fly = build_fly_brain(vocab_size=tokenizer.size, seed=args.seed)
    scr = build_fly_brain(vocab_size=tokenizer.size, seed=args.seed, scrambled=True)
    scr.embed = fly.embed.copy()
    nof = build_no_fly(vocab_size=tokenizer.size, seed=args.seed)

    print("training fly…")
    r_fly = train_fly_level_a(fly, tokenizer, lines, ridge=1e-3, seed=args.seed)
    print("training scramble…")
    r_scr = train_fly_level_a(scr, tokenizer, lines, ridge=1e-3, seed=args.seed)
    print("training no-fly…")
    r_nof = train_no_fly(nof, tokenizer, lines, ridge=1e-3, seed=args.seed)

    prompts = [
        "Once upon a time",
        "The little girl",
        "One day a cat",
        "Tim was sad because",
        "She found a",
    ]
    samples = []
    for i, p in enumerate(prompts[: args.samples]):
        samples.append({"prompt": p, "output": generate(fly, tokenizer, p, max_tokens=40, seed=args.seed + i)})

    meta = {
        "corpus_lines": len(lines),
        "vocab": tokenizer.size,
        "tokenizer_fingerprint": tokenizer.fingerprint,
        "fly_loss": r_fly.final_loss,
        "scramble_loss": r_scr.final_loss,
        "no_fly_loss": r_nof.final_loss,
        "samples": samples,
        "license": "TinyStories CDLA-Sharing-1.0",
    }
    save_checkpoint(args.out, tokenizer=tokenizer, brain=fly, meta=meta)
    print(json.dumps({k: meta[k] for k in meta if k != "samples"}, indent=2))
    print("--- samples ---")
    for s in samples:
        print(f"> {s['prompt']}")
        print(f"  {s['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
