"""Tokenizer encode/decode + fingerprint."""

from __future__ import annotations

from pathlib import Path

from flycast.tokenizer import Tokenizer


def test_roundtrip_and_fingerprint(tmp_path: Path):
    tok = Tokenizer.build(["Hello, world!", "hello there"], max_vocab=100)
    ids = tok.encode("Hello, world!", add_bos=True, add_eos=True)
    assert ids[0] == tok.token_to_id["<bos>"]
    assert ids[-1] == tok.token_to_id["<eos>"]
    text = tok.decode(ids)
    assert "hello" in text
    path = tmp_path / "tok.json"
    tok.save(path)
    loaded = Tokenizer.load(path, expect_fingerprint=tok.fingerprint)
    assert loaded.fingerprint == tok.fingerprint


def test_fingerprint_mismatch(tmp_path: Path):
    tok = Tokenizer.build(["a b c"], max_vocab=50)
    path = tmp_path / "tok.json"
    tok.save(path)
    try:
        Tokenizer.load(path, expect_fingerprint="deadbeefdeadbeef")
        assert False, "expected mismatch"
    except ValueError as exc:
        assert "mismatch" in str(exc)
