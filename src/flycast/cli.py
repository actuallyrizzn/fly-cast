"""CLI: flycast say / flycast overfit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flycast.brain import build_fly_brain
from flycast.generate import generate
from flycast.tokenizer import Tokenizer
from flycast.train import overfit_practice


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flycast", description="Fly Cast — text mouth on fly wiring")
    sub = parser.add_subparsers(dest="cmd", required=True)

    say = sub.add_parser("say", help="Generate a continuation (untrained until you fit a model)")
    say.add_argument("prompt", nargs="+", help="Prompt text")
    say.add_argument("--max-tokens", type=int, default=24)
    say.add_argument("--seed", type=int, default=0)

    of = sub.add_parser("overfit", help="Overfit a tiny practice file (harness gate)")
    of.add_argument("path", type=Path, help="Practice text file")
    of.add_argument("--epochs", type=int, default=60)
    of.add_argument("--seed", type=int, default=0)

    args = parser.parse_args(argv)
    if args.cmd == "say":
        prompt = " ".join(args.prompt)
        # Minimal vocab from prompt alone so CLI works before training artifacts exist.
        tok = Tokenizer.build([prompt, "the a and to of"], max_vocab=256)
        brain = build_fly_brain(vocab_size=tok.size, seed=args.seed)
        out = generate(brain, tok, prompt, max_tokens=args.max_tokens, seed=args.seed)
        print(out or "(empty)")
        return 0
    if args.cmd == "overfit":
        result = overfit_practice(args.path, seed=args.seed, epochs=args.epochs)
        print(
            f"lines={result['lines']} vocab={result['vocab']} "
            f"fly_loss={result['fly_loss']:.4f} "
            f"scramble_loss={result['scramble_loss']:.4f} "
            f"no_fly_loss={result['no_fly_loss']:.4f} "
            f"fly_ok={result['fly_ok']}"
        )
        return 0 if result["fly_ok"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
