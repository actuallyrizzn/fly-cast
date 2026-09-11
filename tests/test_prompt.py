"""Prompt builder tests."""

from __future__ import annotations

import pytest

from flycast.prompt import Event, build_prompt, normalize_cue


def test_build_prompt_gameplay():
    text, cue = build_prompt(
        [Event("HIT"), Event("MISS", "green"), Event("STREAK_8")],
    )
    assert "MISS green" in text
    assert cue == "STREAK"
    assert normalize_cue("score_92") == "SCORE"


def test_build_prompt_chat():
    text, cue = build_prompt([], message="hello fly")
    assert "CHAT hello fly" in text
    assert cue == "CHAT"


def test_build_prompt_empty():
    with pytest.raises(ValueError):
        build_prompt([])
