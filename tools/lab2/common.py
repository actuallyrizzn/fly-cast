"""Lab 2 shared machinery (numpy only, ~2 GB RAM box → everything streams).

Fixes the Lab 1 construction faults:
  * readout trains on ALL pairs (primal ridge, gram is n_neurons², not N²)
  * eval on a real held-out split (hundreds of cue-prefixed lines), not 10 off-distribution lines
  * n-gram floors measured with the same tokenizer / same CE definition
  * batched dense reservoir forward (BLAS) so architecture sweeps take minutes, not hours
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "src"))

from flycast.brain import FlyBrain, build_fly_brain  # noqa: E402
from flycast.connectome import Connectome, load_connectome  # noqa: E402
from flycast.tokenizer import BOS, EOS, Tokenizer  # noqa: E402

LAB2 = ROOT / "artifacts" / "lab2"
DATA = LAB2 / "data"


# --------------------------------------------------------------------------- data


def read_lines(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def cue_of(line: str) -> str:
    return line.split(None, 1)[0].upper() if line.strip() else ""


def encode_lines(tok: Tokenizer, lines: list[str]) -> list[list[int]]:
    bos = tok.token_to_id[BOS]
    eos = tok.token_to_id[EOS]
    out = []
    for ln in lines:
        ids = tok.encode(ln)
        if not ids:
            continue
        out.append([bos] + ids + [eos])
    return out


def n_pairs(seqs: list[list[int]]) -> int:
    return sum(len(s) - 1 for s in seqs)


@dataclass
class Split:
    train: list[str]
    valid: list[str]
    heldout: list[str]
    gold: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, data_dir: Path = DATA) -> "Split":
        gold_p = data_dir / "gold_keep.txt"
        return cls(
            train=read_lines(data_dir / "train.txt"),
            valid=read_lines(data_dir / "valid.txt"),
            heldout=read_lines(data_dir / "heldout.txt"),
            gold=read_lines(gold_p) if gold_p.is_file() else [],
        )


def build_tokenizer(train: list[str], *, max_vocab: int = 4000) -> Tokenizer:
    """Vocab from TRAIN ONLY (Lab 1 built it on train+held — mild leak)."""
    return Tokenizer.build(train, max_vocab=max_vocab)


# --------------------------------------------------------------------------- CE helpers


def ce_from_logits(logits: np.ndarray, targets: np.ndarray) -> float:
    """Mean cross-entropy (nats). logits (N,V) float64, targets (N,) int."""
    x = logits - logits.max(axis=1, keepdims=True)
    lse = np.log(np.exp(x).sum(axis=1))
    picked = x[np.arange(len(targets)), targets]
    return float(np.mean(lse - picked))


def uniform_ce(vocab: int) -> float:
    return math.log(vocab)


# --------------------------------------------------------------------------- n-gram floors


class NGram:
    """Interpolated add-k n-gram (order ≤ 3) — the floor any 'mouth' must beat."""

    def __init__(self, order: int = 3, k: float = 0.1):
        self.order = order
        self.k = k
        self.counts: list[dict[tuple[int, ...], Counter]] = [defaultdict(Counter) for _ in range(order)]
        self.vocab = 0
        self.lams = tuple([1.0 / order] * order)

    def fit(self, seqs: list[list[int]], vocab: int) -> "NGram":
        self.vocab = vocab
        for s in seqs:
            for i in range(1, len(s)):
                for o in range(self.order):
                    if i - o < 0:
                        break
                    ctx = tuple(s[i - o : i])
                    self.counts[o][ctx][s[i]] += 1
        return self

    def _p_order(self, o: int, ctx: tuple[int, ...], tgt: int) -> float:
        c = self.counts[o].get(ctx)
        if not c:
            return 1.0 / self.vocab
        tot = sum(c.values())
        return (c[tgt] + self.k) / (tot + self.k * self.vocab)

    def prob(self, hist: list[int], tgt: int) -> float:
        p = 0.0
        for o in range(self.order):
            ctx = tuple(hist[len(hist) - o :]) if o else ()
            if len(ctx) < o:
                continue
            p += self.lams[o] * self._p_order(o, ctx, tgt)
        return max(p, 1e-12)

    def dist(self, hist: list[int]) -> np.ndarray:
        out = np.zeros(self.vocab, dtype=np.float64)
        for o in range(self.order):
            ctx = tuple(hist[len(hist) - o :]) if o else ()
            if len(ctx) < o:
                continue
            c = self.counts[o].get(ctx)
            if not c:
                out += self.lams[o] / self.vocab
                continue
            tot = sum(c.values())
            base = self.lams[o] * self.k / (tot + self.k * self.vocab)
            out += base
            for t, n in c.items():
                out[t] += self.lams[o] * n / (tot + self.k * self.vocab)
        out /= out.sum()
        return out

    def ce(self, seqs: list[list[int]]) -> float:
        tot = 0.0
        n = 0
        for s in seqs:
            for i in range(1, len(s)):
                tot += -math.log(self.prob(s[:i], s[i]))
                n += 1
        return tot / max(n, 1)

    def tune(self, valid: list[list[int]]) -> "NGram":
        best = (self.ce(valid), self.lams, self.k)
        grid_l = {
            1: [(1.0,)],
            2: [(a, 1 - a) for a in (0.1, 0.2, 0.3, 0.5)],
            3: [(a, b, 1 - a - b) for a in (0.05, 0.1, 0.2) for b in (0.2, 0.3, 0.4, 0.5) if a + b < 1],
        }[self.order]
        for k in (0.01, 0.05, 0.1, 0.5):
            self.k = k
            for lams in grid_l:
                self.lams = lams
                c = self.ce(valid)
                if c < best[0]:
                    best = (c, lams, k)
        self.lams, self.k = best[1], best[2]
        return self

    def sample(self, prompt: list[int], eos: int, *, max_tokens: int = 12, seed: int = 0, temperature: float = 0.8) -> list[int]:
        rng = np.random.default_rng(seed)
        hist = list(prompt)
        out: list[int] = []
        for _ in range(max_tokens):
            p = self.dist(hist)
            if temperature != 1.0:
                p = np.power(p, 1.0 / temperature)
                p /= p.sum()
            nxt = int(rng.choice(len(p), p=p))
            if nxt == eos:
                break
            out.append(nxt)
            hist.append(nxt)
        return out


# --------------------------------------------------------------------------- fast reservoir


@dataclass
class ReservoirCfg:
    embed_dim: int = 32
    radius: float = 0.9
    leak: float = 0.5
    steps: int = 2
    inject_count: int = 64
    input_scale: float = 1.0
    seed: int = 0
    scrambled: bool = False
    skip_last_k: int = 0  # 0 = pure fly features; k>0 appends last-k token embeddings (ablation)

    def key(self) -> str:
        return (
            f"e{self.embed_dim}_r{self.radius}_l{self.leak}_s{self.steps}_i{self.inject_count}"
            f"_x{self.input_scale}_seed{self.seed}_{'scr' if self.scrambled else 'fly'}_k{self.skip_last_k}"
        )

    def to_dict(self) -> dict:
        return dict(self.__dict__)


_CONN: Connectome | None = None


def connectome() -> Connectome:
    global _CONN
    if _CONN is None:
        _CONN = load_connectome()
    return _CONN


class FastReservoir:
    """Batched, dense-matmul twin of FlyBrain.inject_token (verified equal in tests)."""

    def __init__(self, brain: FlyBrain):
        self.brain = brain
        n = brain.n_neurons
        w = np.zeros((n, n), dtype=np.float32)
        np.add.at(w, (brain.syn_pre, brain.syn_post), brain.syn_val)
        self.wt = np.ascontiguousarray(w.T)  # acc = W^T x  (acc[post] += val * x[pre])
        dim = brain.embed.shape[1]
        m = np.zeros((n, dim), dtype=np.float32)
        for i, neuron in enumerate(brain.inject):
            m[int(neuron), i % dim] += 1.0
        self.inject_m = m
        self.n = n

    def drive(self, tokens: np.ndarray) -> np.ndarray:
        """(n, B) drive for a batch of token ids."""
        e = self.brain.embed[tokens].astype(np.float32) * self.brain.input_scale  # (B, dim)
        return self.inject_m @ e.T

    def step(self, x: np.ndarray, drive: np.ndarray) -> np.ndarray:
        a = self.brain.leak
        for _ in range(self.brain.steps):
            x = (1.0 - a) * x + a * np.tanh(drive + self.wt @ x)
        return x

    def iter_states(
        self,
        seqs: list[list[int]],
        *,
        batch_lines: int = 96,
    ) -> Iterator[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
        """Yield (states (P, n) float32, targets (P,), last_tokens (P,), line_ids (P,)) per batch.

        One state per (line, position) where a next token exists — identical to
        flycast.train._collect_fly_examples, but for every line and batched.
        """
        for b0 in range(0, len(seqs), batch_lines):
            chunk = seqs[b0 : b0 + batch_lines]
            B = len(chunk)
            L = max(len(s) for s in chunk)
            ids = np.zeros((B, L), dtype=np.int64)
            lens = np.array([len(s) for s in chunk])
            for i, s in enumerate(chunk):
                ids[i, : len(s)] = s
            line_ids = np.arange(b0, b0 + B)
            x = np.zeros((self.n, B), dtype=np.float32)
            states: list[np.ndarray] = []
            targets: list[np.ndarray] = []
            lasts: list[np.ndarray] = []
            lids: list[np.ndarray] = []
            for t in range(L - 1):
                active = t < lens - 1
                if not active.any():
                    break
                x = self.step(x, self.drive(ids[:, t]))
                states.append(x.T[active])
                targets.append(ids[active, t + 1])
                lasts.append(ids[active, t])
                lids.append(line_ids[active])
            yield (
                np.concatenate(states, axis=0),
                np.concatenate(targets, axis=0),
                np.concatenate(lasts, axis=0),
                np.concatenate(lids, axis=0),
            )


def build_brain(cfg: ReservoirCfg, vocab_size: int) -> FlyBrain:
    return build_fly_brain(
        vocab_size=vocab_size,
        embed_dim=cfg.embed_dim,
        radius=cfg.radius,
        leak=cfg.leak,
        steps=cfg.steps,
        inject_count=cfg.inject_count,
        input_scale=cfg.input_scale,
        seed=cfg.seed,
        scrambled=cfg.scrambled,
        connectome=connectome(),
    )


def features(states: np.ndarray, lasts: np.ndarray, brain: FlyBrain, skip_last_k: int) -> np.ndarray:
    """Readout features: reservoir state (+ optional last-token embedding skip)."""
    if skip_last_k <= 0:
        return states
    emb = brain.embed[lasts].astype(np.float32)
    return np.concatenate([states, emb], axis=1)


# --------------------------------------------------------------------------- primal ridge (streaming)


@dataclass
class RidgeReadout:
    w: np.ndarray  # (F, V) float32
    b: np.ndarray  # (V,) float32
    gain: float = 1.0
    ridge: float = 1.0
    feat_dim: int = 0

    def logits(self, feats: np.ndarray) -> np.ndarray:
        return (feats.astype(np.float64) @ self.w.astype(np.float64) + self.b.astype(np.float64)) * self.gain


def fit_ridge_streaming(
    res: FastReservoir,
    seqs: list[list[int]],
    vocab: int,
    *,
    skip_last_k: int = 0,
    line_weights: np.ndarray | None = None,
    ridges: Iterable[float] = (0.1, 1.0, 10.0, 100.0),
    valid_feats: np.ndarray | None = None,
    valid_targets: np.ndarray | None = None,
    log=print,
) -> tuple[RidgeReadout, dict]:
    """Accumulate XᵀX / XᵀY over all pairs (never storing states), solve, calibrate gain on valid.

    ``line_weights`` (len(seqs),) row weight per line (Grok KEEP upweighting); default 1.0.
    Weighted least squares: rows scaled by √w for the gram, by w for XᵀY.
    """
    F = res.n + (res.brain.embed.shape[1] if skip_last_k else 0) + 1  # + bias
    gram = np.zeros((F, F), dtype=np.float64)
    xty = np.zeros((F, vocab), dtype=np.float64)
    n_rows = 0
    for states, targets, lasts, lids in res.iter_states(seqs):
        x = features(states, lasts, res.brain, skip_last_k).astype(np.float64)
        x = np.concatenate([x, np.ones((x.shape[0], 1))], axis=1)
        if line_weights is not None:
            w = line_weights[lids].astype(np.float64)
            xg = x * np.sqrt(w)[:, None]
            gram += xg.T @ xg
            xy = x * w[:, None]
        else:
            gram += x.T @ x
            xy = x
        # XᵀY with one-hot Y = scatter-add rows by target
        order = np.argsort(targets, kind="stable")
        ts = targets[order]
        xs = xy[order]
        bounds = np.flatnonzero(np.diff(ts)) + 1
        starts = np.concatenate([[0], bounds])
        ends = np.concatenate([bounds, [len(ts)]])
        for s0, e0 in zip(starts, ends):
            xty[:, ts[s0]] += xs[s0:e0].sum(axis=0)
        n_rows += x.shape[0]
    log(f"    gram accumulated over {n_rows} pairs (F={F})")

    best: tuple[float, RidgeReadout] | None = None
    eye = np.eye(F)
    eye[-1, -1] = 0.0  # don't shrink bias
    for lam in ridges:
        w = np.linalg.solve(gram + lam * eye, xty)
        ro = RidgeReadout(w=w[:-1].astype(np.float32), b=w[-1].astype(np.float32), ridge=lam, feat_dim=F - 1)
        if valid_feats is None:
            best = (0.0, ro)
            break
        # gain calibration (softmax temperature) on validation
        base = valid_feats.astype(np.float64) @ w[:-1] + w[-1]
        for gain in (1.0, 2.0, 4.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 64.0, 96.0, 128.0):
            c = ce_from_logits(base * gain, valid_targets)
            if best is None or c < best[0]:
                ro2 = RidgeReadout(w=ro.w, b=ro.b, gain=gain, ridge=lam, feat_dim=F - 1)
                best = (c, ro2)
        log(f"    ridge λ={lam:g}: best valid CE so far {best[0]:.4f} (gain {best[1].gain})")
    assert best is not None
    return best[1], {"valid_ce": best[0], "pairs": n_rows, "ridge": best[1].ridge, "gain": best[1].gain}


def fit_softmax(
    res: FastReservoir,
    seqs: list[list[int]],
    vocab: int,
    *,
    init: RidgeReadout | None = None,
    skip_last_k: int = 0,
    line_weights: np.ndarray | None = None,
    epochs: int = 8,
    lr: float = 2e-3,
    l2: float = 1e-5,
    valid_feats: np.ndarray | None = None,
    valid_targets: np.ndarray | None = None,
    cache_budget_mb: int = 320,
    seed: int = 0,
    log=print,
) -> tuple[RidgeReadout, dict]:
    """Multinomial-logistic readout (the objective we actually report), Adam, streamed.

    Ridge-to-one-hot is a poor CE fitter (Lab 2 run `default`: gain pinned at grid max, λ irrelevant).
    States are cached as float16 when they fit the RAM budget; otherwise recomputed per epoch.
    Early-stops on validation CE. Warm-starts from ``init`` (ridge) when given.
    """
    rng = np.random.default_rng(seed)
    F = res.n + (res.brain.embed.shape[1] if skip_last_k else 0)
    n_rows = sum(len(s) - 1 for s in seqs)
    cache_ok = n_rows * F * 2 / 1e6 <= cache_budget_mb
    cache: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    def batches():
        if cache:
            order = rng.permutation(len(cache))
            for i in order:
                yield cache[i]
            return
        for states, targets, lasts, lids in res.iter_states(seqs):
            x = features(states, lasts, res.brain, skip_last_k)
            w = line_weights[lids].astype(np.float32) if line_weights is not None else np.ones(len(targets), np.float32)
            item = (x.astype(np.float16) if cache_ok else x, targets, w)
            if cache_ok:
                cache.append(item)
            yield item

    if init is not None:
        W = (init.w.astype(np.float32) * init.gain)
        b = (init.b.astype(np.float32) * init.gain)
    else:
        W = (rng.normal(0, 0.01, size=(F, vocab))).astype(np.float32)
        b = np.zeros(vocab, np.float32)
    mW = np.zeros_like(W); vW = np.zeros_like(W)
    mb = np.zeros_like(b); vb = np.zeros_like(b)
    b1, b2, eps = 0.9, 0.999, 1e-8
    step = 0
    best = (float("inf"), W.copy(), b.copy(), 0)
    hist = []
    for ep in range(1, epochs + 1):
        tot = 0.0; cnt = 0.0
        for x16, targets, w in batches():
            x = x16.astype(np.float32)
            logits = x @ W + b
            logits -= logits.max(axis=1, keepdims=True)
            ex = np.exp(logits)
            p = ex / ex.sum(axis=1, keepdims=True)
            nll = -np.log(p[np.arange(len(targets)), targets] + 1e-12)
            tot += float((nll * w).sum()); cnt += float(w.sum())
            p[np.arange(len(targets)), targets] -= 1.0
            p *= (w / w.sum())[:, None]
            gW = x.T @ p + l2 * W
            gb = p.sum(axis=0)
            step += 1
            mW = b1 * mW + (1 - b1) * gW; vW = b2 * vW + (1 - b2) * gW * gW
            mb = b1 * mb + (1 - b1) * gb; vb = b2 * vb + (1 - b2) * gb * gb
            a = lr * math.sqrt(1 - b2 ** step) / (1 - b1 ** step)
            W -= a * mW / (np.sqrt(vW) + eps)
            b -= a * mb / (np.sqrt(vb) + eps)
        train_ce = tot / max(cnt, 1)
        vce = ce_from_logits(valid_feats.astype(np.float64) @ W + b, valid_targets) if valid_feats is not None else train_ce
        hist.append({"epoch": ep, "train_ce": train_ce, "valid_ce": vce})
        log(f"    softmax ep{ep}: train CE {train_ce:.4f}  valid CE {vce:.4f}")
        if vce < best[0]:
            best = (vce, W.copy(), b.copy(), ep)
        elif ep - best[3] >= 2:
            log("    early stop")
            break
    ro = RidgeReadout(w=best[1], b=best[2], gain=1.0, ridge=0.0, feat_dim=F)
    return ro, {"valid_ce": best[0], "best_epoch": best[3], "epochs_run": len(hist), "history": hist, "cached_states": cache_ok}


def collect_features(res: FastReservoir, seqs: list[list[int]], skip_last_k: int) -> tuple[np.ndarray, np.ndarray]:
    """Materialize features for a SMALL split (valid / held-out only)."""
    fs, ts = [], []
    for states, targets, lasts, _lids in res.iter_states(seqs):
        fs.append(features(states, lasts, res.brain, skip_last_k))
        ts.append(targets)
    return np.concatenate(fs), np.concatenate(ts)


# --------------------------------------------------------------------------- generation


def generate_fast(
    res: FastReservoir,
    ro: RidgeReadout,
    tok: Tokenizer,
    prompt: str,
    *,
    skip_last_k: int = 0,
    max_tokens: int = 12,
    min_tokens: int = 2,
    mode: str = "topk",  # greedy | topk | temp
    top_k: int = 8,
    temperature: float = 0.8,
    repetition_penalty: float = 1.3,
    seed: int = 0,
) -> str:
    rng = np.random.default_rng(seed)
    eos = tok.token_to_id[EOS]
    ids = tok.encode(prompt, add_bos=True)
    x = np.zeros((res.n, 1), dtype=np.float32)
    last = ids[0]
    for tid in ids:
        x = res.step(x, res.drive(np.array([tid])))
        last = tid
    out: list[int] = []
    for _ in range(max_tokens):
        feat = features(x.T, np.array([last]), res.brain, skip_last_k)
        logits = ro.logits(feat)[0]
        if out and repetition_penalty > 1.0:
            pen = math.log(repetition_penalty) * max(ro.gain, 1.0)
            for t in set(out):
                logits[t] -= pen
        # never emit specials except EOS
        for sp in ("<pad>", "<unk>", "<bos>", "<sep>"):
            logits[tok.token_to_id[sp]] = -1e9
        if len(out) < min_tokens:
            logits[eos] = -1e9
        if mode == "greedy":
            nxt = int(np.argmax(logits))
        else:
            if mode == "topk":
                idx = np.argpartition(-logits, top_k)[:top_k]
                sub = logits[idx] / temperature
                sub -= sub.max()
                p = np.exp(sub)
                p /= p.sum()
                nxt = int(idx[rng.choice(len(idx), p=p)])
            else:
                z = logits / temperature
                z -= z.max()
                p = np.exp(z)
                p /= p.sum()
                nxt = int(rng.choice(len(p), p=p))
        if nxt == eos:
            break
        out.append(nxt)
        x = res.step(x, res.drive(np.array([nxt])))
        last = nxt
    return tok.decode(out)


# --------------------------------------------------------------------------- misc


def stratified_split(lines: list[str], *, heldout_n: int, valid_n: int, seed: int = 7) -> tuple[list[str], list[str], list[str]]:
    rng = random.Random(seed)
    by_cue: dict[str, list[str]] = defaultdict(list)
    for ln in lines:
        by_cue[cue_of(ln)].append(ln)
    total = len(lines)
    held, valid, train = [], [], []
    for cue, group in sorted(by_cue.items()):
        rng.shuffle(group)
        h = max(1, round(heldout_n * len(group) / total)) if len(group) >= 5 else 0
        v = max(1, round(valid_n * len(group) / total)) if len(group) >= 5 else 0
        held += group[:h]
        valid += group[h : h + v]
        train += group[h + v :]
    rng.shuffle(train)
    return train, valid, held


def jdump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def verify_fast_equals_brain(brain: FlyBrain, tok: Tokenizer, line: str) -> float:
    """Max abs diff between FastReservoir and FlyBrain.inject_token on one line."""
    res = FastReservoir(brain)
    ids = [tok.token_to_id[BOS]] + tok.encode(line)
    brain.reset()
    x = np.zeros((res.n, 1), dtype=np.float32)
    worst = 0.0
    for tid in ids:
        ref = brain.inject_token(tid)
        x = res.step(x, res.drive(np.array([tid])))
        worst = max(worst, float(np.abs(ref - x[:, 0]).max()))
    return worst
