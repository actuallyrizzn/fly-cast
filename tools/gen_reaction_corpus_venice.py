#!/usr/bin/env python3
"""Generate max-useful Fly Hero reaction free-write corpus (templates + Venice).

Target: ~10k–15k unique cue-prefixed lines. Not Common Crawl junk.
Held-out lines in reaction_heldout.txt must never appear.

Usage:
  set -a && . ~/.ssh/venice-api-moya.pass && set +a
  python3 tools/gen_reaction_corpus_venice.py \\
    --out examples/fly_hero/fixtures/reaction_train_v3.txt \\
    --target 12000 --venice-batches 80
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HELDOUT = ROOT / "examples/fly_hero/fixtures/reaction_heldout.txt"
DEFAULT_SEED = ROOT / "examples/fly_hero/fixtures/reaction_train.txt"
VENICE_URL = "https://api.venice.ai/api/v1/chat/completions"
DEFAULT_MODEL = "gemini-3-5-flash-lite"

CUES = [
    "HIT",
    "MISS",
    "STREAK",
    "OVERSTRUM",
    "SONG_START",
    "SONG_END",
    "SCORE",
    "CHAT",
    "SOCIAL",
    "LANE_G",
    "LANE_R",
    "LANE_Y",
    "LANE_B",
    "LANE_O",
]

COLORS = ["green", "red", "yellow", "blue", "orange"]
HIT_VERBS = [
    "nice catch",
    "on time",
    "got it",
    "clean strum",
    "nailed it",
    "right on the beat",
    "solid hit",
    "timing good",
    "hit landed",
    "that one counted",
    "frets lined up",
    "caught it clean",
    "locked in",
    "pocket hit",
    "tight timing",
]
MISS_VERBS = [
    "dropped that one",
    "missed it",
    "that note got away",
    "slipped",
    "lost the note",
    "whiffed that fret",
    "came in late",
    "note escaped",
    "missed the window",
    "late on the fret",
    "fumbled the hit",
    "barely missed",
    "off by a hair",
    "overshot the window",
]
STREAK_VERBS = [
    "streak going",
    "keep it rolling",
    "still hitting",
    "combo climbing",
    "streak is hot",
    "chain still alive",
    "keep the combo",
    "notes in a row",
    "streak holds",
    "riding the streak",
    "still cooking",
    "combo alive",
    "don't drop it",
    "keep stacking",
]
OVER_VERBS = [
    "overstrum — ease up",
    "too early there",
    "wait for it next time",
    "early strum",
    "pulled too soon",
    "hold for the note",
    "back off the strum",
    "ease up next time",
    "don't rush the hit",
    "slow the strum",
]
START_VERBS = [
    "song starting",
    "here we go",
    "highway's live",
    "chart loading",
    "count in",
    "song is live",
    "frets ready",
    "kickoff",
    "intro hits",
    "alright let's go",
]
END_VERBS = [
    "song over",
    "that's a wrap",
    "final chart done",
    "done",
    "chart complete",
    "end of song",
    "last note done",
    "session wrap",
    "finished the chart",
    "run complete",
]
SCORE_VERBS = [
    "score is in",
    "run finished",
    "results are up",
    "score posted",
    "numbers are in",
    "final score up",
    "run scored",
    "tally is in",
    "score dropped",
]
CHAT_VERBS = [
    "heard that",
    "reading chat",
    "got your message",
    "chat noted",
    "message received",
    "reading the line",
    "saw that",
    "copy that",
]
SOCIAL_VERBS = [
    "saw the mention",
    "noting that reply",
    "caught the ping",
    "mention noted",
    "ping received",
    "social line seen",
    "got the @",
    "reply noted",
]

BAD_RE = re.compile(
    r"\b(insect|larva|fly brain|connectome|mosquito|wing|buzz|chrysalis|"
    r"as an ai|language model|certainly!|of course!)\b",
    re.I,
)


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def heldout_banned(heldout: list[str]) -> set[str]:
    banned = set()
    for h in heldout:
        banned.add(normalize(h).lower())
        # also ban bare text without cue if present
        if " " in h and h.split()[0].isupper() and "|" not in h:
            parts = h.split(None, 1)
            if len(parts) == 2 and parts[0] in CUES:
                banned.add(normalize(parts[1]).lower())
    return banned


def ok_line(line: str, banned: set[str]) -> bool:
    line = normalize(line)
    if not line or len(line) > 90:
        return False
    if BAD_RE.search(line):
        return False
    low = line.lower()
    if low in banned:
        return False
    # strip cue for held-out bare match
    parts = line.split(None, 1)
    if len(parts) == 2 and parts[0] in CUES:
        if normalize(parts[1]).lower() in banned:
            return False
        if len(parts[1].split()) > 12:
            return False
    elif len(line.split()) > 12:
        return False
    return True


def template_expand(rng: random.Random) -> list[str]:
    """Dense but useful mouth lines — stems + light spice, not punctuation spam."""
    lines: list[str] = []

    def add(cue: str, text: str) -> None:
        t = normalize(text.rstrip(".!"))
        if not t or len(t.split()) > 10:
            return
        lines.append(t)
        lines.append(f"{cue} {t}")

    hit_cores = HIT_VERBS + [
        "clean hit",
        "pocket timing",
        "right fret",
        "snapped it",
        "banked that hit",
        "on the money",
        "in the window",
        "perfect lane",
        "that counted",
    ]
    miss_cores = MISS_VERBS + [
        "almost",
        "so close",
        "not quite",
        "missed the pocket",
        "off timing",
        "bad window",
        "dropped a fret",
        "lost one",
        "that hurt",
        "reset the chain",
    ]
    streak_cores = STREAK_VERBS + [
        "multiplier up",
        "still locked",
        "holding strong",
        "on a heater",
        "combo intact",
        "stay in it",
        "cooking",
    ]
    over_cores = OVER_VERBS + [
        "chill the strum",
        "wait the note",
        "too greedy",
        "early again",
        "let it come",
    ]
    start_cores = START_VERBS + [
        "loading chart",
        "hands ready",
        "eyes on frets",
        "go time",
        "drop in",
        "chart's up",
    ]
    end_cores = END_VERBS + [
        "lights out",
        "chart cleared",
        "run done",
        "we made it",
        "good set",
    ]
    score_cores = SCORE_VERBS + [
        "board updated",
        "percent in",
        "tally posted",
        "score screen",
    ]
    chat_cores = CHAT_VERBS + [
        "chat check",
        "reading you",
        "noted in chat",
        "eyes on chat",
    ]
    social_cores = SOCIAL_VERBS + [
        "mention logged",
        "social ping",
        "reply clocked",
        "got tagged",
    ]

    for v in hit_cores:
        add("HIT", v)
        for c in COLORS:
            add("HIT", f"{v} on {c}")
            add("HIT", f"clean on {c}")
            add("HIT", f"timed {c}")
            add("HIT", f"caught {c}")
            add("HIT", f"{c} hit")
    for v in miss_cores:
        add("MISS", v)
        for c in COLORS:
            add("MISS", f"{v} on {c}")
            add("MISS", f"dropped {c}")
            add("MISS", f"late on {c}")
            add("MISS", f"slipped on {c}")
            add("MISS", f"whiffed {c}")
            add("MISS", f"missed {c}")
    for v in streak_cores:
        add("STREAK", v)
        add("STREAK", f"{v} strong")
        add("STREAK", f"{v} now")
    for v in over_cores:
        add("OVERSTRUM", v)
        add("OVERSTRUM", f"{v} next time")
    for v in start_cores:
        add("SONG_START", v)
        add("SONG_START", f"{v} now")
    for v in end_cores:
        add("SONG_END", v)
        add("SONG_END", f"{v} now")
    for v in score_cores:
        add("SCORE", v)
    for v in chat_cores:
        add("CHAT", v)
    for v in social_cores:
        add("SOCIAL", v)

    lane_map = {
        "LANE_G": "green",
        "LANE_R": "red",
        "LANE_Y": "yellow",
        "LANE_B": "blue",
        "LANE_O": "orange",
    }
    lane_phrases = [
        "hit {c}",
        "on {c}",
        "{c} lane",
        "fretting {c}",
        "holding {c}",
        "tap {c}",
        "{c} in time",
        "clean {c}",
        "late {c}",
        "early {c}",
        "press {c}",
        "keep {c}",
        "{c} locked",
        "stay on {c}",
        "{c} window",
    ]
    for cue, color in lane_map.items():
        for tmpl in lane_phrases:
            add(cue, tmpl.format(c=color))

    # light useful spice only (~1 in 5 stems)
    extras: list[str] = []
    for line in lines:
        if rng.random() > 0.22:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or parts[0] not in CUES:
            continue
        cue, rest = parts
        bit = rng.choice([" again", " though", " now", " this round"])
        if bit.strip() not in rest:
            extras.append(f"{cue} {normalize(rest + bit)}")
    lines.extend(extras)
    return lines


def venice_chat(api_key: str, model: str, prompt: str, temperature: float = 0.95) -> str:
    body = {
        "model": model,
        "temperature": temperature,
        "max_tokens": 1200,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write short Clone Hero / rhythm-game stream chat reactions. "
                    "Output ONLY lines, one per line. Format: CUE rest of line. "
                    f"CUES allowed: {', '.join(CUES)}. "
                    "Max ~8 words after the cue. Punchy, human, gameplay English. "
                    "No insect/fly/larva cosplay. No essays. No numbering. No quotes."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        VENICE_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def parse_model_lines(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        s = normalize(raw)
        s = re.sub(r"^[\d\.\)\-\*]+\s*", "", s)
        s = s.strip("`\"'")
        if not s:
            continue
        # accept cue-prefixed or bare (we may add cue later)
        out.append(s)
    return out


def venice_batch(api_key: str, model: str, cue: str, n: int, seeds: list[str], rng: random.Random) -> list[str]:
    sample = rng.sample(seeds, min(12, len(seeds))) if seeds else []
    prompt = (
        f"Write {n} distinct {cue} reaction lines for a Fly Hero / Clone Hero stream mouth.\n"
        f"Each line MUST start with `{cue}` then a short English reaction.\n"
        f"Vary wording; cover colors green/red/yellow/blue/orange when relevant.\n"
        f"Style anchors (do not copy verbatim):\n"
        + "\n".join(f"- {s}" for s in sample)
    )
    try:
        text = venice_chat(api_key, model, prompt)
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Venice HTTP {e.code}: {err}") from e
    return parse_model_lines(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--heldout", type=Path, default=DEFAULT_HELDOUT)
    ap.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    ap.add_argument("--target", type=int, default=12000)
    ap.add_argument("--venice-batches", type=int, default=80)
    ap.add_argument("--per-batch", type=int, default=40)
    ap.add_argument("--model", default=os.environ.get("VENICE_MODEL", DEFAULT_MODEL))
    ap.add_argument("--sleep", type=float, default=0.05)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed-int", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed_int)
    banned = heldout_banned(load_lines(args.heldout))
    seed_lines = load_lines(args.seed)

    unique: dict[str, str] = {}

    def ingest(raw: str) -> None:
        line = normalize(raw)
        if not ok_line(line, banned):
            return
        key = line.lower()
        if key not in unique:
            unique[key] = line

    for s in seed_lines:
        ingest(s)
    for t in template_expand(rng):
        ingest(t)

    print(f"after_templates unique={len(unique)}", flush=True)

    api_key = os.environ.get("VENICE_API_KEY") or os.environ.get("VENICE_INFERENCE_KEY")
    venice_ok = 0
    venice_fail = 0
    if api_key and args.venice_batches > 0:
        # weight cues toward gameplay events
        cue_weights = (
            ["HIT"] * 8
            + ["MISS"] * 10
            + ["STREAK"] * 8
            + ["OVERSTRUM"] * 5
            + ["SONG_START"] * 4
            + ["SONG_END"] * 4
            + ["SCORE"] * 3
            + ["CHAT"] * 2
            + ["SOCIAL"] * 2
            + ["LANE_G", "LANE_R", "LANE_Y", "LANE_B", "LANE_O"]
        )
        jobs: list[tuple[int, str, list[str], random.Random]] = []
        for i in range(args.venice_batches):
            cue = rng.choice(cue_weights)
            cue_seeds = [u for u in unique.values() if u.startswith(cue + " ")] or list(
                unique.values()
            )
            # snapshot seeds so workers don't race the live dict
            jobs.append((i, cue, cue_seeds[:24], random.Random(args.seed_int + i * 997)))

        def _run(job: tuple[int, str, list[str], random.Random]):
            i, cue, seeds, jrng = job
            batch = venice_batch(api_key, args.model, cue, args.per_batch, seeds, jrng)
            return i, cue, batch

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futs = [pool.submit(_run, j) for j in jobs]
            for fut in as_completed(futs):
                if len(unique) >= args.target:
                    break
                try:
                    i, cue, batch = fut.result()
                    before = len(unique)
                    for b in batch:
                        if not b.upper().startswith(cue):
                            rest = b
                            if " " in b and b.split()[0].upper() in CUES:
                                rest = b.split(None, 1)[1]
                            b = f"{cue} {rest}"
                        ingest(b)
                    venice_ok += 1
                    print(
                        f"venice[{i+1}/{args.venice_batches}] cue={cue} "
                        f"+{len(unique)-before} unique_total={len(unique)}",
                        flush=True,
                    )
                except Exception as e:
                    venice_fail += 1
                    print(f"venice FAIL {e}", flush=True)
                time.sleep(args.sleep)
    else:
        print("skip_venice: no API key or batches=0", flush=True)

    # Soft cap: prefer Venice diversity over punctuation spam if already past 85% target
    if len(unique) < int(args.target * 0.85):
        fillers = list(unique.values())
        guard = 0
        while len(unique) < args.target and fillers and guard < args.target * 2:
            guard += 1
            base = rng.choice(fillers)
            parts = base.split(None, 1)
            if len(parts) != 2 or parts[0] not in CUES:
                continue
            cue, rest = parts
            color = rng.choice(COLORS)
            variant = normalize(
                rng.choice(
                    [
                        f"{cue} {rest} again",
                        f"{cue} {rest} on {color}",
                        f"{cue} {color} — {rest}",
                        f"{cue} {rest} now",
                    ]
                )
            )
            ingest(variant)

    # Hard useful-cap: if templates overshot, keep a balanced cue mix up to target
    if len(unique) > args.target:
        by_cue: dict[str, list[str]] = {c: [] for c in CUES}
        other: list[str] = []
        for line in unique.values():
            head = line.split()[0]
            if head in CUES:
                by_cue[head].append(line)
            else:
                other.append(line)
        kept: list[str] = []
        # round-robin cues then bare lines
        while len(kept) < args.target:
            progressed = False
            for c in CUES:
                if by_cue[c]:
                    kept.append(by_cue[c].pop(0))
                    progressed = True
                    if len(kept) >= args.target:
                        break
            if len(kept) >= args.target:
                break
            if other:
                kept.append(other.pop(0))
                progressed = True
            if not progressed:
                break
        unique = {k.lower(): k for k in kept}

    ordered = sorted(unique.values(), key=lambda s: (s.split()[0] if s.split()[0] in CUES else "ZZZ", s.lower()))
    header = (
        "# Reaction-shaped free-write train corpus (Fly Hero mouth) v3.\n"
        "# Held-out lines live in reaction_heldout.txt — do not copy them here.\n"
        f"# Generated by tools/gen_reaction_corpus_venice.py target={args.target} "
        f"venice_ok={venice_ok} venice_fail={venice_fail} model={args.model}\n"
        "# Cue-prefixed + bare lines so free-write matches live prompt shape.\n\n"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(header + "\n".join(ordered) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "unique": len(ordered),
                "bytes": args.out.stat().st_size,
                "venice_ok": venice_ok,
                "venice_fail": venice_fail,
                "model": args.model,
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
