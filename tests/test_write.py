"""Additive free-write + checkpoint tests."""

from __future__ import annotations

from pathlib import Path

from flycast.brain import build_fly_brain
from flycast.checkpoint import load_level_a, save_level_a
from flycast.cli import main
from flycast.prompt import Event
from flycast.tokenizer import Tokenizer
from flycast.train import train_fly_level_a
from flycast.write import freewrite


def test_checkpoint_roundtrip_and_freewrite(tmp_path: Path):
    lines = [
        "MISS late on green.",
        "HIT nice catch.",
        "STREAK keep it rolling.",
        "SONG_START here we go.",
        "SONG_END that is a wrap.",
    ]
    tok = Tokenizer.build(lines, max_vocab=200)
    brain = build_fly_brain(vocab_size=tok.size, seed=0, inject_count=32)
    train_fly_level_a(brain, tok, lines, max_pairs=200)
    ckpt = tmp_path / "level_a.npz"
    save_level_a(ckpt, brain, tok)
    loaded, tok2 = load_level_a(ckpt)
    assert tok2.fingerprint == tok.fingerprint
    result = freewrite(loaded, tok2, [Event("MISS", "")], seed=1, min_tokens=2, max_tokens=12)
    assert result.mode == "wrote"
    assert result.text.strip()


def test_cli_write_uses_checkpoint(tmp_path: Path):
    lines = ["MISS dropped that one.", "HIT on time.", "SONG_END song over."]
    tok = Tokenizer.build(lines, max_vocab=120)
    brain = build_fly_brain(vocab_size=tok.size, seed=0, inject_count=16)
    train_fly_level_a(brain, tok, lines, max_pairs=100)
    ckpt = tmp_path / "level_a.npz"
    save_level_a(ckpt, brain, tok)
    assert main(["write", "MISS", "--checkpoint", str(ckpt), "--seed", "1"]) == 0
