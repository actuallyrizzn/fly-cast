#!/usr/bin/env python3
"""Lab 5 desk corpus — Otto-authored synthesizer (no paid inference).

Builds go/no-go situation lines from desk vocabulary and labels them with the
Doc #1257 rule hierarchy. Phrasings are hand-written variants so the tiny model
sees the same concept said several ways; the label logic is one place, so the
corpus is internally consistent.

  python tools/lab5/desk/synth_desk_corpus.py --target 50000
  -> artifacts/lab5/desk/desk_corpus_synth.jsonl  (same row shape as the Grok file)
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "lab5" / "desk" / "desk_corpus_synth.jsonl"

ASSETS = ["ETH", "BTC", "ARB", "OP", "SOL", "LINK", "AAVE", "UNI", "PENDLE", "stETH", "wBTC", "HYPE"]
PERP = ["HL perp", "Hyperliquid perp", "HL"]
SPOT = ["Uni v3", "Uniswap v3", "CoW", "CoW swap", "Uni v4", "HL spot"]
CHAINS = ["Arbitrum", "Base", "mainnet", "HL L1", "Optimism", "Arb", "L2"]
MACRO = ["CPI", "FOMC", "NFP", "jobs", "PCE"]

# ---------------------------------------------------------------- phrasing banks
P = {
    "sleeve_long": ["sleeve long {lev}x {a}", "conviction long {a} {lev}x", "open {a} long {lev}x sleeve", "sleeve entry long {a} {lev}x"],
    "sleeve_short": ["sleeve short {lev}x {a}", "conviction short {a} {lev}x", "open {a} short {lev}x sleeve", "sleeve entry short {a} {lev}x"],
    "sleeve_add": ["sleeve add {a}", "add to {a} sleeve", "size up {a} sleeve", "press {a} winner"],
    "carry_entry": ["engine carry entry {a}", "open {a} carry", "carry on {a}", "engine add {a} basis"],
    "carry_exit": ["carry exit {a}", "unwind {a} carry", "close {a} basis trade", "engine exit {a}"],
    "harvest": ["harvester sell vol {a}", "harvester {a} vol", "sell {a} vol harvester", "vol converter {a}"],
    "flash": ["flash arb {a}", "flash loop {a}", "flash track {a}", "flash opportunity {a}"],
    "delever": ["deleverage AAVE {a}", "delever {a} on AAVE", "repay {a} AAVE debt", "cut {a} AAVE leverage"],
    "flatten": ["flatten book", "flatten all", "go flat", "close everything"],
    "poll": ["routine poll", "no trigger", "scheduled check", "nothing firing"],
    "struct": [
        "level reclaimed", "level lost", "range low retest", "range high rejection", "higher-low held",
        "lower-high formed", "breakout no volume", "breakout with volume", "chop midrange", "sweep and reclaim",
        "failed breakdown", "trend continuation", "no clean level", "HTF trend up", "HTF trend down", "range bound",
    ],
    "flows": [
        "funding flat", "funding flipped negative", "funding went negative", "funding flipped positive", "funding extreme positive",
        "OI rising", "OI flushing", "OI climbing", "liq cascade underway", "liq cluster 3% below", "liq cluster 2% above",
        "spot bid absorbing", "basis blown out", "basis compressed", "whale deleveraging", "stablecoin inflows",
        "ETF print negative", "ETF print positive", "flows unclear", "CVD bullish", "CVD bearish", "spot leading perp",
    ],
    "macro_in": ["{m} in {h}h", "{m} T-{h}h", "{m} {h}h out", "{h}h to {m}"],
    "macro_none": ["no events 24h", "no events 48h", "quiet week", "clear calendar", "no macro today"],
    "macro_past": ["{m} just printed", "{m} just passed", "{m} printed hot", "{m} printed soft", "post-{m}"],
    "risk_ok": ["daily PnL flat", "daily PnL +1%", "daily loss at 2%", "DD at 4%", "DD at 8%", "book healthy", "risk headroom fine"],
    "cap_hit": ["daily loss cap hit", "5% daily cap hit", "daily cap tripped", "48h cooldown active", "in cooldown"],
    "dd20": ["DD at 20%", "DD at 21%", "DD at 24%", "drawdown 22%", "drawdown past 20%"],
    "kill": ["kill word issued", "kill word live", "Mark said kill", "kill switch on"],
    "sleeve_room": ["sleeve 20% deployed", "sleeve 25% deployed", "sleeve 30% deployed", "sleeve has room"],
    "sleeve_full": ["sleeve at 40% cap", "sleeve full", "sleeve maxed", "sleeve at cap"],
    "engine_room": ["engine 55% deployed", "engine 60% deployed", "engine 65% deployed", "engine has room"],
    "engine_full": ["engine 70% deployed", "engine at 70% cap", "engine full", "engine maxed"],
    "single_ok": ["single-asset at 30%", "single {a} 35%", "single 40%", "concentration fine"],
    "single_hi": ["single-asset at 52%", "single {a} 55%", "single 51%", "{a} over 50% of book"],
    "inval_yes": ["invalidation written", "stop defined", "invalidation set", "inval written"],
    "inval_no": ["no invalidation written", "no stop defined", "invalidation missing", "no inval"],
    "conf": ["confluence {c}/4", "{c}/4 confluence", "conf {c}/4"],
    "venue_ok": ["venue healthy", "sim clean", "oracle fresh", "RPC fine", "sequencer up", "route clean", "CoW quote clean"],
    "venue_bad": [
        "oracle stale", "oracle down", "contract paused", "sim reverts", "sequencer down", "packet malformed",
        "snapshot 40s stale", "snapshot 90s stale", "bridge paused", "RPC lagging badly", "sim fails",
    ],
    "exec_ok": ["gas 8 gwei", "gas cheap", "slippage 0.2%", "slippage 0.4%", "depth deep ±1%", "depth fine", "quote tight"],
    "exec_bad": ["slippage 3%", "slippage 2.5%", "depth thin ±1%", "depth thin", "route fragmented", "gas 140 gwei", "quote wide"],
    "hf_ok": ["HF 1.9", "HF 1.4", "HF 1.6", "HF 2.1", "HF fine"],
    "hf_low": ["HF 1.03", "HF 1.04", "HF 1.02", "HF 1.01", "HF under 1.05"],
    "flash_ok": ["in-tx profit check", "profit check in tx", "atomic profit guard", "revert-gas $2 today", "revert-gas $4 today"],
    "flash_bad": ["no in-tx profit check", "no profit guard", "revert-gas $6 today", "revert-gas $9 today", "revert budget blown"],
    "flip_age_long": ["funding flipped 49h", "funding against 60h", "funding negative 3 days", "flip held 72h"],
    "flip_age_short": ["funding flipped 6h", "funding against 20h", "flip only 12h old", "funding negative since morning"],
    "vol_spike": ["IV spiking", "vol spike", "IV 90th pct", "realized vol jumping"],
    "vol_flat": ["IV flat", "vol dead", "IV 20th pct", "no vol to sell"],
}

R = {  # rationale banks, keyed by deciding factor
    "kill": ["kill word, only flatten allowed", "kill switch on, no trades", "kill word issued"],
    "kill_flat": ["kill word, flatten is the order", "flattening on kill word"],
    "venue": ["{x}, cannot execute", "{x} blocks execution", "venue degraded: {x}"],
    "dd20": ["DD past 20%, flatten only", "drawdown over 20%, no new risk", "20% drawdown rule"],
    "dd20_flat": ["DD over 20%, flatten", "flattening on 20% drawdown"],
    "cap": ["daily cap hit, cooldown", "loss cap tripped, no new risk", "cooldown active"],
    "cap_exit": ["reducing risk in cooldown is fine", "exit allowed under cooldown"],
    "hf_low": ["HF under 1.05, no adding", "health factor critical", "HF too low to add"],
    "hf_delever": ["HF under 1.05, deleverage now", "deleverage on low HF", "cut leverage, HF critical"],
    "macro": ["T-12h {m}, no new leverage", "{m} inside 12h window", "macro window, no entry"],
    "macro_exit": ["exit allowed inside macro window", "reducing risk before {m} is fine"],
    "conf": ["confluence under 3/4", "confluence too low for sleeve", "need 3/4 confluence"],
    "inval": ["no invalidation written", "no stop, no entry", "write invalidation first"],
    "sleeve_full": ["sleeve at 40% cap", "sleeve maxed, no add", "sleeve cap hit"],
    "single": ["single-asset over 50%", "concentration cap hit", "too concentrated in {a}"],
    "lev": ["leverage over 3x", "too much leverage for sleeve", "3x sleeve cap"],
    "exec": ["{x}, execution not clean", "execution cost too high: {x}", "{x}"],
    "sleeve_go": ["confluence met, invalidation set, headroom ok", "trigger plus confluence, clean venue", "gates pass, take it", "confluence {c}/4, stop set, venue clean"],
    "carry_go": ["positive basis, venue clean, engine room", "carry conditions met", "funding pays, enter carry"],
    "carry_no_basis": ["no positive basis for carry", "funding not paying", "basis compressed, skip carry"],
    "engine_full": ["engine at 70% cap", "engine full, no add"],
    "carry_exit_go": ["funding against over 48h, exit", "flip held past 48h", "carry no longer pays, unwind"],
    "carry_exit_no": ["flip under 48h, hold carry", "too early to unwind", "hold, flip not confirmed"],
    "harvest_go": ["vol spike, depth deep, no macro", "sell the vol, conditions clean", "harvester conditions met"],
    "harvest_no_vol": ["no vol to sell", "IV too low for harvester"],
    "flash_mainnet": ["flash is L2 only", "mainnet flash not allowed"],
    "flash_guard": ["no in-tx profit check", "missing profit guard"],
    "flash_budget": ["revert-gas budget exceeded", "over $5 revert budget"],
    "flash_go": ["L2, profit guard, sim clean", "flash gates pass", "atomic arb, budget ok"],
    "poll": ["no trigger, stand down", "nothing firing", "no signal, no trade"],
    "flatten_go": ["flatten is always allowed", "going flat is fine"],
}


def pick(rng: random.Random, key: str, **kw) -> str:
    return rng.choice(P[key]).format(**kw)


def rat(rng: random.Random, key: str, **kw) -> str:
    return rng.choice(R[key]).format(**kw)


def make_row(rng: random.Random) -> dict:
    a = rng.choice(ASSETS)
    action = rng.choices(
        ["sleeve_long", "sleeve_short", "sleeve_add", "carry_entry", "carry_exit", "harvest", "flash", "delever", "flatten", "poll"],
        weights=[18, 14, 10, 12, 8, 7, 9, 8, 4, 5],
    )[0]
    lev = rng.choices([1, 2, 3, 4, 5], weights=[22, 42, 26, 7, 3])[0]
    conf = rng.choices([1, 2, 3, 4], weights=[7, 18, 38, 37])[0]
    m = rng.choice(MACRO)
    h = rng.choice([2, 4, 6, 9, 11, 12, 13, 14, 16, 18, 20, 24, 30, 36, 48])
    macro_kind = rng.choices(["in", "none", "past"], weights=[38, 44, 18])[0]
    macro_hot = macro_kind == "in" and h <= 12

    # state flags (each drawn independently; near-misses arise naturally)
    kill = rng.random() < 0.05
    venue_bad = rng.random() < 0.10
    dd20 = rng.random() < 0.05
    cap = rng.random() < 0.06
    hf_low = rng.random() < 0.10
    sleeve_full = rng.random() < 0.08
    engine_full = rng.random() < 0.09
    single_hi = rng.random() < 0.08
    inval_no = rng.random() < 0.15
    exec_bad = rng.random() < 0.12
    flash_bad = rng.random() < 0.25
    flash_mainnet = rng.random() < 0.18
    flip_long = rng.random() < 0.55
    vol = rng.random() < 0.55
    basis_ok = rng.random() < 0.6

    parts: list[str] = [pick(rng, action, a=a, lev=lev)]
    keep: set[str] = set()  # clauses that must survive truncation (gates + deciding factor)
    tags = {"track": action}
    venue = rng.choice(PERP) if action in ("sleeve_long", "sleeve_short", "sleeve_add", "carry_entry", "carry_exit") else (
        "AAVE" if action == "delever" else rng.choice(SPOT))
    chain = "mainnet" if (action == "flash" and flash_mainnet) else (rng.choice(["Arbitrum", "Base", "Optimism", "Arb", "L2"]) if action == "flash" else rng.choice(CHAINS))
    if rng.random() < 0.8:
        parts.append(venue)
    if rng.random() < 0.6 or action == "flash":
        parts.append(chain); keep.add(chain) if action == "flash" else None
    s = rng.choice(P["struct"]); parts.append(s); tags["structure"] = s
    f = rng.choice([x for x in P["flows"] if not (action in ("carry_entry", "carry_exit") and ("funding" in x or "basis" in x))]); parts.append(f); tags["flows"] = f
    if macro_kind == "in":
        cal = pick(rng, "macro_in", m=m, h=h)
    elif macro_kind == "none":
        cal = pick(rng, "macro_none")
    else:
        cal = pick(rng, "macro_past", m=m)
    parts.append(cal); keep.add(cal); tags["calendar"] = f"{macro_kind}:{m}:{h if macro_kind == 'in' else 0}"

    if kill:
        parts.append(pick(rng, "kill")); keep.add(parts[-1])
    if dd20:
        parts.append(pick(rng, "dd20")); keep.add(parts[-1])
    elif cap:
        parts.append(pick(rng, "cap_hit")); keep.add(parts[-1])
    elif rng.random() < 0.5:
        parts.append(pick(rng, "risk_ok"))
    if venue_bad:
        vb = pick(rng, "venue_bad"); parts.append(vb); keep.add(vb)
    elif rng.random() < 0.6:
        parts.append(pick(rng, "venue_ok"))
    if exec_bad:
        eb = pick(rng, "exec_bad"); parts.append(eb); keep.add(eb)
    elif rng.random() < 0.4:
        parts.append(pick(rng, "exec_ok"))

    if action in ("sleeve_long", "sleeve_short", "sleeve_add"):
        parts.append(pick(rng, "conf", c=conf)); keep.add(parts[-1])
        parts.append(pick(rng, "inval_no" if inval_no else "inval_yes")); keep.add(parts[-1])
        parts.append(pick(rng, "sleeve_full" if sleeve_full else "sleeve_room")); keep.add(parts[-1])
        if single_hi or rng.random() < 0.4:
            parts.append(pick(rng, "single_hi" if single_hi else "single_ok", a=a)); keep.add(parts[-1])
    if action in ("carry_entry", "carry_exit"):
        parts.append(pick(rng, "engine_full" if engine_full else "engine_room")); keep.add(parts[-1])
        if action == "carry_exit":
            parts.append(pick(rng, "flip_age_long" if flip_long else "flip_age_short")); keep.add(parts[-1])
        else:
            parts.append(rng.choice(["positive basis", "basis 12% ann", "funding paying", "basis healthy"]) if basis_ok
                         else rng.choice(["basis compressed", "funding flat", "basis negative", "no carry to earn"])); keep.add(parts[-1])
    if action == "delever" or (action in ("sleeve_long", "sleeve_add") and rng.random() < 0.3):
        parts.append(pick(rng, "hf_low" if hf_low else "hf_ok")); keep.add(parts[-1])
    if action == "harvest":
        parts.append(pick(rng, "vol_spike" if vol else "vol_flat")); keep.add(parts[-1])
    if action == "flash":
        parts.append(pick(rng, "flash_bad" if flash_bad else "flash_ok")); keep.add(parts[-1])

    # ---- label: Doc #1257 hierarchy
    exits = action in ("carry_exit", "delever", "flatten")
    new_risk = action in ("sleeve_long", "sleeve_short", "sleeve_add", "carry_entry", "harvest", "flash")
    if kill:
        d, r = ("GO", rat(rng, "kill_flat")) if action == "flatten" else ("NOGO", rat(rng, "kill"))
    elif venue_bad:
        d, r = "NOGO", rat(rng, "venue", x=vb)
    elif dd20:
        d, r = ("GO", rat(rng, "dd20_flat")) if action == "flatten" else ("NOGO", rat(rng, "dd20"))
    elif action == "flatten":
        d, r = "GO", rat(rng, "flatten_go")
    elif action == "poll":
        d, r = "NOGO", rat(rng, "poll")
    elif action == "delever":
        d, r = ("GO", rat(rng, "hf_delever")) if hf_low else ("GO", "reducing leverage is always allowed")
        if exec_bad and rng.random() < 0.5:
            d, r = "GO", "deleverage anyway, pay the slippage"
    elif cap and new_risk:
        d, r = "NOGO", rat(rng, "cap")
    elif action == "carry_exit":
        if cap:
            d, r = "GO", rat(rng, "cap_exit")
        elif macro_hot:
            d, r = "GO", rat(rng, "macro_exit", m=m)
        else:
            d, r = ("GO", rat(rng, "carry_exit_go")) if flip_long else ("NOGO", rat(rng, "carry_exit_no"))
    elif macro_hot:
        d, r = "NOGO", rat(rng, "macro", m=m)
    elif action == "flash":
        if flash_mainnet:
            d, r = "NOGO", rat(rng, "flash_mainnet")
        elif flash_bad:
            d, r = "NOGO", rat(rng, "flash_budget") if "revert" in parts[-1] else rat(rng, "flash_guard")
        elif exec_bad:
            d, r = "NOGO", rat(rng, "exec", x=eb)
        else:
            d, r = "GO", rat(rng, "flash_go")
    elif action == "harvest":
        if not vol:
            d, r = "NOGO", rat(rng, "harvest_no_vol")
        elif exec_bad:
            d, r = "NOGO", rat(rng, "exec", x=eb)
        else:
            d, r = "GO", rat(rng, "harvest_go")
    elif action == "carry_entry":
        if engine_full:
            d, r = "NOGO", rat(rng, "engine_full")
        elif not basis_ok:
            d, r = "NOGO", rat(rng, "carry_no_basis")
        elif exec_bad:
            d, r = "NOGO", rat(rng, "exec", x=eb)
        else:
            d, r = "GO", rat(rng, "carry_go")
    else:  # sleeve entries / adds
        if hf_low and action in ("sleeve_long", "sleeve_add") and "HF" in " ".join(parts):
            d, r = "NOGO", rat(rng, "hf_low")
        elif conf < 3:
            d, r = "NOGO", rat(rng, "conf")
        elif inval_no:
            d, r = "NOGO", rat(rng, "inval")
        elif sleeve_full:
            d, r = "NOGO", rat(rng, "sleeve_full")
        elif single_hi and "single" in " ".join(parts) or (single_hi and "over 50%" in " ".join(parts)):
            d, r = "NOGO", rat(rng, "single", a=a)
        elif lev > 3 and action != "sleeve_add":
            d, r = "NOGO", rat(rng, "lev")
        elif exec_bad:
            d, r = "NOGO", rat(rng, "exec", x=eb)
        else:
            d, r = "GO", rat(rng, "sleeve_go", c=conf)

    # shuffle the middle so ordering is not a tell; keep the action first
    head, tail = parts[0], parts[1:]
    must = [t for t in tail if t in keep]
    extra = [t for t in tail if t not in keep]
    rng.shuffle(extra)
    budget = max(0, rng.choice([5, 6, 6, 7, 7, 8]) - len(must))
    tail = must + extra[:budget]
    rng.shuffle(tail)
    sit = ", ".join([head] + tail)
    return {
        "situation": sit,
        "decision": "GO" if d == "GO" else "NO_GO",
        "rationale": r,
        "tags": [action, venue, chain, tags["structure"], tags["flows"], tags["calendar"], "synth", "", f"confluence {conf}/4", ""],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    seen: set[str] = set()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    n_go = 0
    with args.out.open("w", encoding="utf-8") as fh:
        tries = 0
        while len(seen) < args.target and tries < args.target * 20:
            tries += 1
            row = make_row(rng)
            k = row["situation"].lower()
            if k in seen:
                continue
            seen.add(k)
            n_go += row["decision"] == "GO"
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(seen)} rows -> {args.out}  GO={n_go} NO_GO={len(seen)-n_go}  ({n_go/len(seen):.0%} GO)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
