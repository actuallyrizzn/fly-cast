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

    pk = sub.add_parser("pick", help="Pick a reply from candidates given a prompt")
    pk.add_argument("prompt", help="Prompt / cue text")
    pk.add_argument("candidates", nargs="+", help="Candidate reply strings")
    pk.add_argument("--seed", type=int, default=0)

    rp = sub.add_parser("replay", help="Replay events.jsonl into picked reactions")
    rp.add_argument("events", type=Path)
    rp.add_argument("--bank", type=Path, default=None)
    rp.add_argument("--guard", action="store_true", help="Run lines through safety guard")
    rp.add_argument("--stop-path", type=Path, default=None, help="Kill-switch file path")
    rp.add_argument("--line-log", type=Path, default=None, help="Append JSONL line log")

    gd = sub.add_parser("guard", help="Check one line through the safety guard")
    gd.add_argument("text", nargs="+", help="Candidate mouth line")
    gd.add_argument("--cues", default="", help="Cue string for the log")
    gd.add_argument("--mode", default="picked")
    gd.add_argument("--stop-path", type=Path, default=None)
    gd.add_argument("--line-log", type=Path, default=None)

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
    if args.cmd == "pick":
        from flycast.picker import pick

        tok = Tokenizer.build([args.prompt, *args.candidates], max_vocab=512)
        brain = build_fly_brain(vocab_size=tok.size, seed=args.seed)
        result = pick(brain, tok, args.prompt, list(args.candidates))
        print(f"mode={result.mode} score={result.score:.4f}")
        print(result.text)
        return 0
    if args.cmd == "replay":
        from flycast.guard import Guard
        from flycast.replay import replay

        guard = None
        if args.guard or args.stop_path or args.line_log:
            guard = Guard(
                stop_path=args.stop_path or (Path.home() / "fly-cast" / "STOP"),
                log_path=args.line_log,
            )
        for line in replay(args.events, bank_path=args.bank, guard=guard):
            print(line)
        return 0
    if args.cmd == "guard":
        from flycast.guard import Guard

        g = Guard(
            stop_path=args.stop_path or (Path.home() / "fly-cast" / "STOP"),
            log_path=args.line_log,
        )
        result = g.check(" ".join(args.text), cues=args.cues, mode=args.mode)
        print(f"allowed={result.allowed} reason={result.reason} mode={result.mode}")
        print(result.filtered or "(silent)")
        return 0 if result.allowed else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
