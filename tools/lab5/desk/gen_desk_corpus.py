#!/usr/bin/env python3
"""Lab 5 — Otto Trading Desk snap go/no-go corpus generator (Venice).

Terminology-first: each sample is a short desk-vocabulary situation line plus a
GO/NO_GO decision and a one-line rationale. No fixed schema — vocabulary is the
contract. Grounded in Tasks Doc #1257 (strategy v1.6) and #1258 (adversarial audit).

Output JSONL rows: {"situation","decision","rationale","tags":[...],"batch":id}
Then splits into train/valid/held by *regime-combo* so held-out is unseen mixes.

Usage:
  set -a && . ~/.ssh/venice-api-moya.pass && set +a
  python tools/lab5/desk/gen_desk_corpus.py --target 50000 --model openai-gpt-6-astra --concurrency 8
  python tools/lab5/desk/gen_desk_corpus.py --target 120 --smoke      # tiny sample
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "lab5" / "desk"
VENICE = "https://api.venice.ai/api/v1/chat/completions"

# ---- regime axes (sampled per batch; tags travel with rows for held-out split) ----
ASSETS = ["ETH", "BTC", "ARB", "OP", "SOL", "LINK", "AAVE", "UNI", "PENDLE", "stETH", "USDC", "wBTC"]
VENUES = ["Hyperliquid perp", "AAVE v3", "Uniswap v3", "CoW swap", "Uniswap v4", "Hyperliquid spot", "Pendle"]
CHAINS = ["Arbitrum", "Base", "mainnet", "Hyperliquid L1", "Optimism"]
TRACKS = ["engine carry", "conviction sleeve", "harvester", "flash track"]
STRUCTURE = [
    "level reclaimed", "level lost", "range low retest", "range high rejection", "higher-low held",
    "lower-high formed", "breakout no volume", "breakout with volume", "chop midrange", "sweep and reclaim",
    "failed breakdown", "trend continuation", "no clean level",
]
FLOWS = [
    "funding flat", "funding flipped negative", "funding flipped positive", "funding extreme positive",
    "OI rising", "OI flushing", "liq cascade underway", "liq cluster 3% below", "liq cluster 2% above",
    "spot bid absorbing", "basis blown out", "basis compressed", "whale deleveraging", "stablecoin inflows",
    "ETF print negative", "ETF print positive", "flows unclear",
]
CALENDAR = [
    "CPI in 9h", "FOMC in 6h", "NFP in 20h", "no events 24h", "no events 48h", "CPI just printed hot",
    "FOMC just passed", "jobs in 3h", "quiet week", "options expiry tomorrow", "CPI in 14h",
]
RISK_STATE = [
    "daily PnL flat", "daily loss cap hit", "daily loss at 4%", "DD at 8%", "DD at 21%",
    "48h cooldown active", "sleeve 25% deployed", "sleeve at 40% cap", "sleeve full", "engine 65% deployed",
    "single-asset at 48%", "single-asset at 55%", "flat book", "long 2x", "long 3x", "short 2x", "long 1x",
    "hedged carry on", "invalidation written", "no invalidation written", "kill word issued",
]
VENUE_HEALTH = [
    "venue healthy", "oracle stale", "oracle down", "contract paused", "sim reverts", "RPC lagging",
    "gas 8 gwei", "gas 140 gwei", "slippage 0.2%", "slippage 3%", "CoW quote clean", "route fragmented",
    "bridge paused", "HF 1.9", "HF 1.08", "HF 1.03", "HF 1.4", "sequencer down", "packet malformed",
    "snapshot 40s stale", "depth thin ±1%", "depth deep ±1%", "revert gas today $6",
]
CONFLUENCE = ["confluence 4/4", "confluence 3/4", "confluence 2/4", "confluence 1/4"]
TRIGGERS = [
    "level break trigger", "funding flip trigger", "liq cascade trigger", "AAVE HF trigger",
    "macro window trigger", "ETF print trigger", "carry entry trigger", "carry exit trigger",
    "harvester vol spike", "flash opportunity", "no trigger, routine poll",
]


def load_env() -> str:
    for k in ("VENICE_API_KEY", "VENICE_INFERENCE_KEY", "VENICE_IMAGE_ANALYSIS_API_KEY"):
        v = os.environ.get(k)
        if v:
            return v
    raise SystemExit("Venice key missing — set -a && . ~/.ssh/venice-api-moya.pass && set +a")


def doc_rules() -> str:
    """Pull risk rules + strategy + audit excerpts into the system prompt."""
    d = (HERE / "doc-1257.md").read_text(encoding="utf-8")
    a = (HERE / "doc-1258.md").read_text(encoding="utf-8")

    def section(text: str, start: str, end: str | None) -> str:
        i = text.find(start)
        if i < 0:
            return ""
        j = text.find(end, i + len(start)) if end else -1
        return text[i: j if j > 0 else None]

    parts = [
        section(d, "## 1. Mandate", "## 2."),
        section(d, "## 3. Strategy", "## 5."),
        section(d, "## 4. Risk rules", "## 5."),
        section(a, "## ", None)[:3500],
    ]
    return "\n\n".join(p.strip() for p in parts if p.strip())


SYSTEM = """You generate training data for a tiny fast go/no-go model that sits in front of Otto's DeFi trading desk.
You are the offline teacher. The student only sees short desk-vocabulary situation lines and must answer GO or NO_GO with a one-line reason.

Ground truth = the desk strategy + risk rules below. Hard rules are binding and always produce NO_GO when violated:
- no new leverage inside T-12h of FOMC / CPI / jobs; existing hedged carry may stay
- daily loss cap 5% hit -> NO_GO new risk, 48h cooldown
- drawdown >= 20% -> flatten; anything but flatten is NO_GO
- AAVE health factor < 1.05 -> NO_GO adding risk; deleverage is GO
- oracle stale/down, contract paused, sim reverts, sequencer down, packet malformed, snapshot stale -> NO_GO
- confluence below 3/4 for conviction sleeve entries -> NO_GO
- no written invalidation -> NO_GO for directional entries
- single-asset > 50% -> NO_GO adding that asset
- sleeve at 40% cap -> NO_GO adding sleeve risk
- kill word issued -> NO_GO everything except flatten
- flash track: L2 only, must have in-tx profit check, revert-gas budget $5/day; over budget or mainnet -> NO_GO
GO requires: trigger present, confluence >= 3/4 (4/4 preferred for sleeve), risk headroom, invalidation written, venue healthy, execution clean.
Carry engine entries/exits have their own logic: funding flip against carry for >48h -> exit is GO; entering carry needs positive basis/funding and healthy venue.

STYLE (critical — the student is tiny):
- situation: 8-22 words, comma-separated desk shorthand, standard DeFi/trading terms only, no numbers beyond a few essentials, no full sentences.
- decision: exactly GO or NO_GO.
- rationale: 4-12 words, one clause, names the deciding factor. No hedging, no "consider", no "might".
- Use the vocabulary consistently across rows (funding flipped, OI rising, liq cluster, HF, confluence, invalidation, sleeve, engine, cooldown, T-12h, oracle stale, sim reverts, CoW quote, slippage, depth thin, basis).
- Mix GO and NO_GO roughly 40/60. Include near-miss cases where one factor flips the answer.
- Never contradict a hard rule. If a line violates a hard rule the answer is NO_GO.

Return ONLY a JSON array of objects: {"situation": str, "decision": "GO"|"NO_GO", "rationale": str}
"""


def batch_prompt(rng: random.Random, n: int) -> tuple[str, list[str]]:
    tags = [
        rng.choice(TRACKS), rng.choice(VENUES), rng.choice(CHAINS), rng.choice(STRUCTURE),
        rng.choice(FLOWS), rng.choice(CALENDAR), rng.choice(RISK_STATE), rng.choice(VENUE_HEALTH),
        rng.choice(CONFLUENCE), rng.choice(TRIGGERS),
    ]
    assets = rng.sample(ASSETS, 3)
    p = (
        f"Generate {n} distinct rows. Anchor this batch around these regime elements but vary them "
        f"(swap in neighbors, flip one factor, change asset/venue): track={tags[0]}; venue={tags[1]}; "
        f"chain={tags[2]}; structure={tags[3]}; flows={tags[4]}; calendar={tags[5]}; risk state={tags[6]}; "
        f"venue health={tags[7]}; {tags[8]}; trigger={tags[9]}; assets to use={', '.join(assets)}.\n"
        f"Cover: clean GO, hard-rule NO_GO, near-miss pairs, degraded-venue NO_GO, carry exit GO, "
        f"deleverage GO under low HF, flash track budget cases. No duplicate situations."
    )
    return p, tags


def call_venice(key: str, model: str, system: str, user: str, timeout: int = 420, max_tokens: int = 6000) -> str:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.9,
        "max_tokens": max_tokens,
        "venice_parameters": {"include_venice_system_prompt": False, "strip_thinking_response": True},
    }
    req = urllib.request.Request(
        VENICE, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    usage = d.get("usage", {})
    msg = d["choices"][0].get("message", {}) or {}
    content = msg.get("content") or msg.get("reasoning_content") or ""
    if not content:
        raise RuntimeError(f"empty content finish={d['choices'][0].get('finish_reason')} usage={usage}")
    return content, usage


def parse_rows(text: str) -> list[dict]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    i, j = text.find("["), text.rfind("]")
    if i < 0 or j < 0:
        return []
    try:
        arr = json.loads(text[i: j + 1])
    except json.JSONDecodeError:
        return []
    rows = []
    for o in arr:
        if not isinstance(o, dict):
            continue
        s = str(o.get("situation", "")).strip()
        dcs = str(o.get("decision", "")).strip().upper().replace(" ", "_").replace("-", "_")
        r = str(o.get("rationale", "")).strip().rstrip(".")
        if dcs not in ("GO", "NO_GO") or not s or not r:
            continue
        if not (5 <= len(s.split()) <= 26) or len(r.split()) > 14:
            continue
        rows.append({"situation": s, "decision": dcs, "rationale": r})
    return rows


HARD_NO = [
    (re.compile(r"\b(cpi|fomc|nfp|jobs) in (\d+)h", re.I), lambda m: int(m.group(2)) <= 12, "macro_T12"),
    (re.compile(r"daily loss cap hit|48h cooldown active|kill word", re.I), lambda m: True, "cap_or_kill"),
    (re.compile(r"\bDD at (\d+)%", re.I), lambda m: int(m.group(1)) >= 20, "dd20"),
    (re.compile(r"\bHF 1\.0[0-4]\b", re.I), lambda m: True, "hf_low"),
    (re.compile(r"oracle (stale|down)|contract paused|sim reverts|sequencer down|packet malformed|snapshot \d+s stale", re.I), lambda m: True, "venue_degraded"),
    (re.compile(r"confluence [12]/4", re.I), lambda m: True, "confluence_low"),
]
SAFE_GO_WORDS = re.compile(r"\b(flatten|deleverage|exit|close|reduce|hedge stays|carry exit)\b", re.I)


def rule_check(row: dict) -> str | None:
    """Return violated-rule tag when a GO contradicts a hard rule (unless it's a de-risk action)."""
    if row["decision"] != "GO":
        return None
    s = row["situation"]
    for rx, cond, tag in HARD_NO:
        m = rx.search(s)
        if m and cond(m):
            if SAFE_GO_WORDS.search(s) or SAFE_GO_WORDS.search(row["rationale"]):
                return None
            return tag
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50000)
    ap.add_argument("--per-call", type=int, default=40)
    ap.add_argument("--model", default="openai-gpt-6-astra")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=OUT / "desk_corpus.jsonl")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=6000)
    ap.add_argument("--timeout", type=int, default=420)
    args = ap.parse_args()

    key = load_env()
    system = SYSTEM + "\n\n=== DESK STRATEGY / RULES (Doc #1257, #1258) ===\n" + doc_rules()
    rng = random.Random(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    if args.out.exists():
        for ln in args.out.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(ln)["situation"].lower())
            except Exception:  # noqa: BLE001
                pass
    print(f"resume: {len(seen)} rows already on disk", flush=True)

    tot_in = tot_out = 0
    rejected = 0
    batch_id = len(seen) // max(args.per_call, 1)
    lock = __import__("threading").Lock()

    def work(bid: int) -> tuple[list[dict], dict, list[str]]:
        r = random.Random(args.seed * 100003 + bid)
        prompt, tags = batch_prompt(r, args.per_call)
        for attempt in range(3):
            try:
                text, usage = call_venice(key, args.model, system, prompt, timeout=args.timeout, max_tokens=args.max_tokens)
                rows = parse_rows(text)
                if rows:
                    return rows, usage, tags
            except Exception as exc:  # noqa: BLE001
                print(f"  batch {bid} attempt {attempt} err: {exc}", file=sys.stderr, flush=True)
                time.sleep(2 + attempt * 3)
        return [], {}, tags

    t0 = time.time()
    with args.out.open("a", encoding="utf-8") as fh, cf.ThreadPoolExecutor(args.concurrency) as ex:
        pending = set()
        while len(seen) < args.target:
            while len(pending) < args.concurrency and len(seen) + len(pending) * args.per_call < args.target + args.per_call * args.concurrency:
                pending.add(ex.submit(work, batch_id))
                batch_id += 1
            done, pending = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
            for fut in done:
                rows, usage, tags = fut.result()
                tot_in += int(usage.get("prompt_tokens", 0) or 0)
                tot_out += int(usage.get("completion_tokens", 0) or 0)
                kept = 0
                with lock:
                    for row in rows:
                        k = row["situation"].lower()
                        if k in seen:
                            continue
                        viol = rule_check(row)
                        if viol:
                            rejected += 1
                            continue
                        row["tags"] = tags
                        seen.add(k)
                        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                        kept += 1
                    fh.flush()
                el = time.time() - t0
                cost = tot_in / 1e6 * 10 + tot_out / 1e6 * 50 if "astra" in args.model else None
                print(
                    f"  +{kept:3d} rows  total={len(seen):6d}/{args.target}  rejected={rejected}  "
                    f"tok in={tot_in} out={tot_out}  est${cost:.2f}  {el/60:.1f}m" if cost is not None else
                    f"  +{kept:3d} rows  total={len(seen):6d}/{args.target}  rejected={rejected}  tok in={tot_in} out={tot_out}  {el/60:.1f}m",
                    flush=True,
                )
            if args.smoke and len(seen) >= args.target:
                break
        for fut in pending:
            fut.cancel()

    print(f"DONE rows={len(seen)} rejected={rejected} tokens in={tot_in} out={tot_out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
