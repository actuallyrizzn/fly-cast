"""Latency on a tiny reservoir returns the keys the card names."""

import numpy as np

from flycast.jevlab.arms import ArmCfg, build_reservoir
from flycast.jevlab.data import load_split, smoke_root
from flycast.jevlab.latency import packet_latency_ms
from flycast.jevlab.readout import Head
from flycast.jevlab.vectors import build_embed, load_glove
from flycast.tokenizer import Tokenizer


def test_packet_latency_on_smoke() -> None:
    root = smoke_root()
    rows = load_split("sst2", "train", root=root)
    texts = [text for text, _label in rows]
    tok = Tokenizer.build(texts, max_vocab=20000)
    glove = load_glove(root / "glove.mini.txt", set(tok.id_to_token))
    cfg = ArmCfg(0.5, 1, 0.9, 32, 1.0, "last", 0)
    embed, _coverage = build_embed(tok, glove, cfg.inject_count, cfg.seed)
    res = build_reservoir(cfg, tok, embed, scrambled=False)
    head = Head(
        w=np.zeros((res.n, 2), dtype=np.float32),
        b=np.zeros(2, dtype=np.float32),
        temperature=1.0,
        kind="ridge",
        lam=1.0,
        mu=np.zeros(res.n, dtype=np.float32),
        sd=np.ones(res.n, dtype=np.float32),
    )
    got = packet_latency_ms(tok, res, head, texts, pooling="last", n=5, seed=0)
    assert got["median_ms"] > 0
    assert set(got) >= {"median_ms", "p90_ms", "p99_ms", "mean_tokens", "n", "cpu", "threads"}
    assert got["n"] == 5
