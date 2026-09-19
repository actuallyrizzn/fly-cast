"""Score a finished run. Refuses without grid_done. publishable is computed."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from flycast.jevlab.scorer import ARMS, evaluate, publishable


def _bad_split(run_dir: Path) -> str | None:
    folder = run_dir / "metrics"
    if not folder.is_dir():
        return "missing metrics directory"
    for path in folder.glob("*.json"):
        if "_test" not in path.name:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("split") != "test":
            return f"{path.name} is named test but split={payload.get('split')!r}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args(argv)
    run_dir = args.run_dir.expanduser()
    if not (run_dir / "grid_done").exists():
        print("missing grid_done", file=sys.stderr)
        return 3
    reason = _bad_split(run_dir)
    if reason:
        print(reason, file=sys.stderr)
        return 3
    result = evaluate(run_dir, args.protocol)
    result["publishable"] = publishable([result])
    (run_dir / "score.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for arm in ARMS:
        mean, lo, hi = result["arms"][arm]["acc"]
        brier = result["arms"][arm]["brier"][0]
        ece = result["arms"][arm]["ece"][0]
        print(f"{arm} | {mean:.3f} [{lo:.3f}, {hi:.3f}] | {brier:.3f} | {ece:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
