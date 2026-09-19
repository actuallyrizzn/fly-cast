"""GloVe projection: specials stay zero, one seed gives one matrix."""

from pathlib import Path

import numpy as np

from flycast.jevlab.vectors import build_embed, load_glove
from flycast.tokenizer import BOS, EOS, PAD, SEP, UNK, Tokenizer


def _glove_file(tmp_path: Path) -> Path:
    rows = {
        "good": np.ones(100, dtype=np.float32),
        "bad": np.full(100, 2.0, dtype=np.float32),
        "film": np.full(100, 3.0, dtype=np.float32),
        "actor": np.full(100, 4.0, dtype=np.float32),
        "plot": np.full(100, 5.0, dtype=np.float32),
        "scene": np.full(100, 6.0, dtype=np.float32),
    }
    path = tmp_path / "mini.txt"
    lines = [" ".join([word, *map(str, vec.tolist())]) for word, vec in rows.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_build_embed_specials_oov_and_seed(tmp_path: Path) -> None:
    path = _glove_file(tmp_path)
    tok = Tokenizer.from_tokens((PAD, UNK, BOS, EOS, SEP, "good", "missing"))
    glove = load_glove(path, set(tok.token_to_id))
    assert set(glove) == {"good"}
    embed, coverage = build_embed(tok, glove, 8, 0)
    assert embed.shape == (tok.size, 8)
    assert float(coverage) == 0.5
    for special in (PAD, UNK, BOS, EOS, SEP):
        assert np.all(embed[tok.token_to_id[special]] == 0.0)
    mean = glove["good"]
    rng = np.random.default_rng(0)
    projection = rng.normal(0.0, 1.0 / np.sqrt(100), size=(100, 8)).astype(np.float32)
    assert np.allclose(embed[tok.token_to_id["missing"]], mean @ projection)
    again, _ = build_embed(tok, glove, 8, 0)
    assert np.array_equal(embed, again)
