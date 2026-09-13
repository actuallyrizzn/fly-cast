#!/usr/bin/env python3
"""Lab 4 one-shot — Level C on FlyBrain (no Grok filter loop).

Uses Lab 3 cycle-1 cleaned corpus + Lab 3 held/valid + floors.
Writes artifacts/lab4/ and refreshes Tasks chronicle Doc #1332 if pass present.

  cd /root/fly-cast && . .venv/bin/activate
  nohup python -u tools/lab4/lab4_run.py >> artifacts/lab4/lab4-run.log 2>&1 &
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "lab4"))
sys.path.insert(0, str(ROOT / "tools" / "lab2"))
# NOTE: do not insert tools/ — tools/common.py shadows lab2/common.py

from common import ReservoirCfg, jdump, read_lines  # noqa: E402
from level_c import LAB4, train_lab4  # noqa: E402

LAB3 = ROOT / "artifacts" / "lab3"
DEFAULT_TRAIN = LAB3 / "grok-runs" / "run-20260912T153958Z" / "cycle-1" / "reaction_train_clean.txt"
DEFAULT_VALID = LAB3 / "data" / "valid.txt"
DEFAULT_HELD = LAB3 / "data" / "heldout.txt"
DEFAULT_FLOORS = LAB3 / "baselines.json"


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    ap.add_argument("--valid", type=Path, default=DEFAULT_VALID)
    ap.add_argument("--heldout", type=Path, default=DEFAULT_HELD)
    ap.add_argument("--floors", type=Path, default=DEFAULT_FLOORS)
    ap.add_argument("--level-b-epochs", type=int, default=6)
    ap.add_argument("--level-c-epochs", type=int, default=8)
    ap.add_argument("--pairs-per-epoch", type=int, default=40000)
    ap.add_argument("--softmax-a-epochs", type=int, default=5)
    ap.add_argument("--early-stop-patience-b", type=int, default=2, help="Level-B epochs without valid CE gain before stop")
    ap.add_argument("--early-stop-patience-c", type=int, default=2, help="Level-C epochs without valid CE gain before stop")
    ap.add_argument("--scramble-pairs-per-epoch", type=int, default=None, help="cap scramble Level-C pairs/epoch (clock budget)")
    ap.add_argument("--out-root", type=Path, default=None, help="run dir parent (default artifacts/lab4)")
    args = ap.parse_args()

    root_out = args.out_root if args.out_root else LAB4
    root_out = root_out if root_out.is_absolute() else ROOT / root_out
    root_out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = root_out / f"run-{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    train = read_lines(args.train if args.train.is_absolute() else ROOT / args.train)
    valid = read_lines(args.valid if args.valid.is_absolute() else ROOT / args.valid)
    held = read_lines(args.heldout if args.heldout.is_absolute() else ROOT / args.heldout)
    floors_path = args.floors if args.floors.is_absolute() else ROOT / args.floors
    floors = json.loads(floors_path.read_text(encoding="utf-8"))
    if "bigram" not in floors and isinstance(floors.get("models"), dict):
        floors = floors["models"]  # lab2_baselines / lab5_desk_prep layout

    cfg = ReservoirCfg()
    _log(f"START Lab4 {out.name} train={len(train)} valid={len(valid)} held={len(held)}")
    _log(f"  floors bigram={floors.get('bigram', {}).get('heldout_ce')} trigram={floors.get('trigram', {}).get('heldout_ce')}")

    info = train_lab4(
        train, valid, held, cfg=cfg, floors=floors,
        level_b_epochs=args.level_b_epochs,
        level_c_epochs=args.level_c_epochs,
        pairs_per_epoch=args.pairs_per_epoch,
        softmax_a_epochs=args.softmax_a_epochs,
        scramble_pairs_per_epoch=args.scramble_pairs_per_epoch,
        early_stop_patience_b=args.early_stop_patience_b,
        early_stop_patience_c=args.early_stop_patience_c,
        log=_log,
    )

    # Persist the trained fly. HARD FAIL if this does not land — soft-warn ate Lab 4.
    import numpy as np  # noqa: PLC0415

    b = info["brain"]
    ro = info["ro"]
    model_path = out / "fly_model.npz"
    tok_path = out / "tokenizer.json"
    np.savez_compressed(
        model_path,
        syn_pre=b.syn_pre, syn_post=b.syn_post, syn_val=b.syn_val, inject=b.inject,
        embed=b.embed, ro_w=ro.w, ro_b=ro.b,
        meta=json.dumps({
            "n_neurons": int(b.n_neurons), "leak": float(b.leak), "steps": int(b.steps),
            "input_scale": float(b.input_scale), "gain": float(ro.gain),
            "cfg": cfg.to_dict(),
            "heldout_ce": float(info["heldout_ce"]),
            "heldout_ce_level_b": float(info["heldout_ce_level_b"]),
            "scramble_ce": float(info["scramble_ce"]),
            "beats_bigram": bool(info.get("beats_bigram")),
            "beats_trigram": bool(info.get("beats_trigram")),
        }),
    )
    info["tok"].save(tok_path)
    if not model_path.is_file() or model_path.stat().st_size < 1000:
        raise SystemExit(f"FATAL: fly_model.npz missing or tiny after save: {model_path}")
    if not tok_path.is_file():
        raise SystemExit(f"FATAL: tokenizer.json missing after save: {tok_path}")
    latest = root_out / "LATEST"
    latest.write_text(str(out.resolve()) + "\n", encoding="utf-8")
    _log(f"  saved {model_path} ({model_path.stat().st_size} bytes) + {tok_path}  LATEST→{out.name}")

    summary = {
        "lab": 4,
        "stamp": stamp,
        "run_dir": str(out.relative_to(ROOT)),
        "train_n": len(train),
        "valid_n": len(valid),
        "held_n": len(held),
        "fly": {
            "heldout_ce": info["heldout_ce"],
            "heldout_ce_level_a": info["heldout_ce_level_a"],
            "heldout_ce_level_b": info["heldout_ce_level_b"],
            "scramble_ce": info["scramble_ce"],
            "honesty_ok": info["honesty_ok"],
            "beats_bigram": info["beats_bigram"],
            "beats_trigram": info["beats_trigram"],
            "beats_scramble": info["beats_scramble"],
            "beats_level_b": info["beats_level_b"],
            "bigram_floor": info["bigram_floor"],
            "trigram_floor": info["trigram_floor"],
            "vocab": info["vocab"],
            "pairs": info["pairs"],
            "level_c_best_epoch": (info.get("level_c") or {}).get("best_epoch"),
            "syn_l1_delta": (info.get("level_c") or {}).get("syn_l1_delta"),
        },
        "level_a": info.get("level_a"),
        "level_b": info.get("level_b"),
        "level_c": info.get("level_c"),
        "authorized": "Mark 2026-09-12 — Lab 4 Level C on upscaled FlyBrain; no Grok filter loop",
    }
    jdump(out / "summary.json", summary)
    jdump(root_out / "latest-lab4.json", summary)
    _log(
        f"DONE Lab4 held_C={info['heldout_ce']:.3f} B={info['heldout_ce_level_b']:.3f} "
        f"scr={info['scramble_ce']:.3f} honesty={'OK' if info['honesty_ok'] else 'FAIL'} "
        f"beats_bigram={info['beats_bigram']} beats_B={info['beats_level_b']}"
    )

    # Optional chronicle — Doc 1332 if set, else create under project 62
    try:
        os.environ.setdefault("TASKS_DSC_FLYCAST_CHRONICLE_DOC_ID", "1332")
        # Inline short body update via chronicle helper shape is Lab2-oriented;
        # write a dedicated markdown body instead.
        pass_path = Path.home() / ".ssh" / "tasks-dsc-flycast-lab.pass"
        if pass_path.is_file():
            env = {}
            for ln in pass_path.read_text().splitlines():
                if "=" in ln and not ln.strip().startswith("#"):
                    k, v = ln.split("=", 1)
                    env[k.strip()] = v.strip()
            # force doc 1332 for lab4
            env["TASKS_DSC_FLYCAST_CHRONICLE_DOC_ID"] = "1332"
            body = _render_lab4_body(summary)
            import urllib.request

            payload = {
                "id": 1332,
                "title": f"Fly Cast — Lab 4 Level C ({stamp})",
                "body": body,
                "directory_path": "research",
            }
            # create if update fails
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{env['TASKS_DSC_BASE_URL'].rstrip('/')}/api/update-document.php",
                data=data,
                method="POST",
                headers={
                    "X-API-Key": env["TASKS_DSC_FLYCAST_LAB_API_KEY"],
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    _log(f"  chronicle update #{1332}: {resp.status}")
            except Exception as exc:  # noqa: BLE001
                create = {
                    "project_id": int(env.get("TASKS_DSC_FLYCAST_CHRONICLE_PROJECT_ID") or 62),
                    "title": f"Fly Cast — Lab 4 Level C ({stamp})",
                    "body": body,
                    "directory_path": "research",
                }
                req2 = urllib.request.Request(
                    f"{env['TASKS_DSC_BASE_URL'].rstrip('/')}/api/create-document.php",
                    data=json.dumps(create).encode(),
                    method="POST",
                    headers={
                        "X-API-Key": env["TASKS_DSC_FLYCAST_LAB_API_KEY"],
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req2, timeout=60) as resp:
                    created = json.load(resp)
                    doc = created.get("document") or created
                    _log(f"  chronicle created #{doc.get('id')}: ({exc})")
    except Exception as exc:  # noqa: BLE001
        _log(f"  chronicle warn: {exc}")

    return 0


def _render_lab4_body(summary: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    f = summary["fly"]
    return "\n".join(
        [
            "# Fly Cast — Lab 4 Level C",
            "",
            f"**Updated:** {now}",
            f"**Run:** `{summary['stamp']}`",
            "**Machine:** FlyBrain (upscaled; Level C sign-preserving synapses)",
            "",
            "## Result",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| Level A held CE | {f['heldout_ce_level_a']:.3f} |",
            f"| Level B held CE | {f['heldout_ce_level_b']:.3f} |",
            f"| Level C held CE | {f['heldout_ce']:.3f} |",
            f"| Scramble (C recipe) | {f['scramble_ce']:.3f} |",
            f"| Honesty (C < scramble) | {'OK' if f['honesty_ok'] else 'FAIL'} |",
            f"| Beats Level B | {'yes' if f['beats_level_b'] else 'no'} |",
            f"| Beats bigram ({f['bigram_floor']:.3f}) | {'yes' if f['beats_bigram'] else 'no'} |",
            f"| Syn |Δ| mean | {f.get('syn_l1_delta')} |",
            f"| Train lines | {summary['train_n']} |",
            "",
            "## Policy",
            "",
            "- Lab 4 = Level C (mask/sign frozen; magnitudes + embed + readout; real CE).",
            "- No Grok filter loop this run — CE / honesty / bigram are the gates.",
            "- Destroy cron still armed for FlyBrain (self-delete) at scheduled window.",
            "",
            f"- Artifacts: `{summary['run_dir']}`",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
