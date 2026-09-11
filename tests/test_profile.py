"""Product profile loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from flycast.profile import load_profile

ROOT = Path(__file__).resolve().parents[1]


def test_load_fly_hero_profile():
    p = load_profile(ROOT / "examples" / "fly_hero")
    assert p.name == "fly_hero"
    assert p.bank_path.is_file()
    assert p.lexicon_path.is_file()
    assert "MISS" in p.known_cues
    assert "MISS" in p.interesting_cues
    assert p.should_react("MISS", "")
    assert p.should_react("HIT", "STRUM")
    assert not p.should_react("HIT", "HAMMER")
    assert p.lexicon_scale == 0.85


def test_load_via_toml_path():
    p = load_profile(ROOT / "examples" / "fly_hero" / "profile.toml")
    assert p.root == (ROOT / "examples" / "fly_hero").resolve()


def test_missing_profile_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_profile(tmp_path)


def test_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    dest = tmp_path / "custom"
    dest.mkdir()
    (dest / "profile.toml").write_text(
        'name = "custom"\n'
        "[paths]\nbank = \"b.tsv\"\nlexicon = \"l.tsv\"\n"
        "[cues]\nknown = [\"EVENT\"]\ninteresting = [\"EVENT\"]\n",
        encoding="utf-8",
    )
    (dest / "b.tsv").write_text("EVENT\thello\n", encoding="utf-8")
    (dest / "l.tsv").write_text("hello\t1.0\n", encoding="utf-8")
    monkeypatch.setenv("FLYCAST_PROFILE", str(dest))
    p = load_profile(None)
    assert p.name == "custom"
    assert p.should_react("EVENT", "")
