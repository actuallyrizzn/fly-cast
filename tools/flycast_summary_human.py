#!/usr/bin/env python3
"""Ensure Grok SUMMARY.md has human-facing prose outside the rates table.

If Grok skips BLUF / implications / plain-English failure modes, Otto rewrites
those sections from grades.jsonl and preserves any rates table Grok already wrote.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path


_REQUIRED_MARKERS = (
    "bluf",
    "implication",
    "what this means",
    "for the product",
    "next cycle",
    "next lab",
    "free-write",
    "free write",
)


def _strip_tables(md: str) -> str:
    out: list[str] = []
    for ln in md.splitlines():
        s = ln.strip()
        if s.startswith("|"):
            continue
        if re.fullmatch(r"\|?[\s\-:|]+\|?", s):
            continue
        out.append(ln)
    return "\n".join(out).strip()


def summary_needs_human_rewrite(summary_path: Path | None) -> bool:
    """True if SUMMARY is missing or lacks human-facing prose outside the table."""
    if summary_path is None or not summary_path.is_file():
        return True
    raw = summary_path.read_text(encoding="utf-8")
    if not raw.strip():
        return True
    prose = _strip_tables(raw)
    if len(prose) < 280:
        return True
    low = prose.lower()
    hits = sum(1 for m in _REQUIRED_MARKERS if m in low)
    # Need at least two implication-style anchors, or a clear BLUF block
    if "bluf" in low and hits >= 2:
        return False
    if hits >= 3 and len(prose) >= 500:
        return False
    return True


def _rate_table(by_src: dict[str, Counter]) -> str:
    lines = [
        "| source | n | KEEP | REWRITE | CUT | pass |",
        "|--------|---|------|---------|-----|------|",
    ]
    tot = Counter()
    for src in ("probe", "climb", "train"):
        c = by_src.get(src) or Counter()
        n = sum(c.values())
        k, rw, cut = c["KEEP"], c["REWRITE"], c["CUT"]
        for k2, v in c.items():
            tot[k2] += v
        pass_r = (k / n) if n else 0.0
        lines.append(f"| {src} | {n} | {k} | {rw} | {cut} | {pass_r:.1%} |")
    n = sum(tot.values())
    k, rw, cut = tot["KEEP"], tot["REWRITE"], tot["CUT"]
    pass_r = (k / n) if n else 0.0
    lines.append(f"| **all** | **{n}** | **{k}** | **{rw}** | **{cut}** | **{pass_r:.1%}** |")
    return "\n".join(lines)


def _extract_existing_table(md: str) -> str | None:
    rows: list[str] = []
    in_table = False
    for ln in md.splitlines():
        if ln.strip().startswith("|"):
            in_table = True
            rows.append(ln.rstrip())
        elif in_table:
            break
    if len(rows) >= 3:
        return "\n".join(rows)
    return None


def rewrite_summary_human(
    *,
    grades: list[dict],
    summary_path: Path,
    cycle: int | None = None,
    prior_note: str = "",
) -> str:
    """Write/overwrite SUMMARY.md with table + Otto human prose. Returns body."""
    by_src: dict[str, Counter] = defaultdict(Counter)
    cut_whys: list[str] = []
    cut_examples: list[str] = []
    keep_examples: list[str] = []
    for g in grades:
        src = (g.get("source") or "unknown").lower()
        v = (g.get("verdict") or "").upper()
        by_src[src][v] += 1
        text = (g.get("text") or "").strip()
        why = (g.get("why") or "").strip()
        if v == "CUT" and why and len(cut_whys) < 12:
            cut_whys.append(why)
        if v == "CUT" and text and len(cut_examples) < 5:
            cut_examples.append(text[:80])
        if v == "KEEP" and text and len(keep_examples) < 4:
            keep_examples.append(text[:80])

    probe = by_src["probe"]
    train = by_src["train"]
    pn = sum(probe.values())
    pk = probe["KEEP"]
    tn = sum(train.values())
    tk = train["KEEP"]
    trw = train["REWRITE"]
    probe_r = (pk / pn) if pn else 0.0
    train_r = (tk / tn) if tn else 0.0
    salvage_r = ((tk + trw) / tn) if tn else 0.0

    if probe_r >= 0.5:
        mouth = (
            "Free-write is getting close to something you could put in front of a player — "
            "enough probe lines already sound like real chat."
        )
    elif probe_r > 0:
        mouth = (
            "A few probe lines landed, but free-write is still not ready for the live game. "
            "Keep the picker as the default mouth."
        )
    else:
        mouth = (
            "Probe free-write still produced nothing Grok would keep. "
            "Players should not hear free-write in the live game yet — picker stays the mouth."
        )

    if train_r >= 0.35:
        corpus = (
            f"Training data is improving in a real way: about {train_r:.0%} of the graded train slice "
            f"already sounds lane-true ({tk}/{tn} KEEP; salvage including rewrites ~{salvage_r:.0%})."
        )
    elif train_r >= 0.2:
        corpus = (
            f"Training data is climbing but still messy — roughly {train_r:.0%} KEEP on the train slice "
            f"({tk}/{tn}). Better than mush-only, not yet a clean corpus."
        )
    else:
        corpus = (
            f"Training data is still mostly cut-worthy ({tk}/{tn} KEEP, ~{train_r:.0%}). "
            "The filter is doing heavy lifting; do not celebrate volume alone."
        )

    # Failure modes from why strings (cluster rough keywords)
    blobs = " ".join(cut_whys).lower()
    modes: list[tuple[str, str]] = []
    checks = [
        (
            "mush|word.?salad|ungrounded|token",
            "Word salad / no mechanic",
            "The line is shuffled words with no fret, color, or miss named — "
            "a player hears noise, not a reaction.",
        ),
        (
            "cue|misalign|wrong (cue|lane)",
            "Wrong vibe for the cue",
            "A miss sounds like a win (or the reverse) — chat would feel tone-deaf.",
        ),
        (
            "bot|telemetry|processed|tracked|system",
            "Bot / system voice",
            "Sounds like a log line (“message processed”) instead of a human in chat.",
        ),
        (
            "host|recap|gg everyone|wrap|trophy",
            "Host / DJ closer",
            "Song-end lines sound like a radio host, not a kick-chat reaction.",
        ),
        (
            "cheer|caps|lfg|omg|hype",
            "Cheerleading salt",
            "ALL-CAPS hype or coach talk — stream chat usually stays quieter and sharper.",
        ),
    ]
    for pat, title, why_m in checks:
        if re.search(pat, blobs) and len(modes) < 5:
            ex = next((e for e in cut_examples if e), "")
            modes.append((title, f"{why_m}" + (f' Example cut: “{ex}”.' if ex else "")))
    while len(modes) < 3 and cut_whys:
        w = cut_whys[len(modes)]
        modes.append(("Repeated cut reason", w if w.endswith(".") else w + "."))
        if len(modes) >= 5:
            break
    if not modes:
        modes = [
            (
                "Most cuts lack a named body",
                "Keep requiring a color/fret/mechanic so lines stay grounded in the chart.",
            )
        ]

    next_cycle = (
        "Next cycle: keep cutting mush hard, bias the corpus toward lines that name the body "
        "(color, fret, sustain, overstrum), and watch whether probe KEEP blinks above zero."
    )
    if probe_r == 0 and train_r >= 0.3:
        next_cycle = (
            "Next cycle / next lab: train KEEP is moving but probe is stuck at zero — "
            "the free-write path (or hybrid) is the bottleneck, not only the corpus filter. "
            "Design the next lab around closing that gap, not just more train volume."
        )
    elif probe_r >= 0.5:
        next_cycle = (
            "Next cycle: protect KEEP quality, widen cue coverage, and decide whether free-write "
            "can leave the lab as an additive mouth beside the picker."
        )

    keep_line = ""
    if keep_examples:
        keep_line = "Examples Grok kept: " + "; ".join(f"“{k}”" for k in keep_examples[:3]) + "."

    existing = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
    table = _extract_existing_table(existing) or _rate_table(by_src)

    cyc = f"cycle {cycle}" if cycle is not None else "this cycle"
    parts = [
        "# Mouth-taste grade summary",
        "",
        "Pass = KEEP only. REWRITE is salvage, not a pass.",
        "",
        table,
        "",
        "## BLUF",
        "",
        f"For {cyc}: {mouth} {corpus}",
        keep_line,
        prior_note.strip(),
        "",
        "## What this means",
        "",
        "- **Product mouth:** picker stays the live default until probe KEEP is honestly useful "
        f"(this round: {pk}/{pn} probe KEEP, {probe_r:.0%}).",
        f"- **Training corpus:** {tk}/{tn} KEEP on the graded train slice (~{train_r:.0%}); "
        f"salvage (KEEP+REWRITE) ~{salvage_r:.0%}.",
        "- **Lab design:** use this round to decide whether the next lab should spend more "
        "compute on free-write/hybrid, or keep squeezing the train filter.",
        "",
        "## Top failure modes (plain English)",
        "",
    ]
    for title, body in modes[:5]:
        parts.append(f"- **{title}.** {body}")
    parts += [
        "",
        "## Implications for the next cycle / next lab",
        "",
        next_cycle,
        "",
        "## Filter rules (dumb cuts Otto can ship)",
        "",
        "- Cut when the line has no lane/mechanic word (green/red/blue/fret/sustain/streak/FC/overstrum/…) "
        "and is not in a tiny vernacular whitelist (`saved it`, `still cooking`, …).",
        "- Cut when it reads like a system log (`processed`, `tracked`, `noted`, `in real-time`).",
        "- Cut when the cue and the line disagree (SCORE that says choke; SONG_END that says miss; etc.).",
        "- Cut host/DJ closers on song end (`GG everyone`, `next track`, `done and dusted`).",
        "- Cut cheer salt (`LFG`, `OMG`, multi-sentence essays).",
        "",
        "_Prose outside the rates table rewritten by Otto when Grok left it thin or engineer-only._",
        "",
    ]
    # drop empty prior_note blank
    body = "\n".join(p for p in parts if p is not None)
    body = re.sub(r"\n{3,}", "\n\n", body)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep Grok original beside rewrite
    if existing.strip() and summary_needs_human_rewrite(summary_path):
        (summary_path.parent / "SUMMARY.grok-raw.md").write_text(existing, encoding="utf-8")
    summary_path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
    return body


def ensure_human_summary(
    cycle_dir: Path,
    grades: list[dict],
    *,
    cycle: int | None = None,
) -> tuple[Path, bool]:
    """Return (summary_path, rewritten). Rewrites if human prose missing/thin."""
    summary_path = cycle_dir / "out" / "SUMMARY.md"
    if not summary_needs_human_rewrite(summary_path):
        return summary_path, False
    rewrite_summary_human(grades=grades, summary_path=summary_path, cycle=cycle)
    return summary_path, True
