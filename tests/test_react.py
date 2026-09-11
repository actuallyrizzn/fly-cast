"""React helper tests."""

from __future__ import annotations

from flycast.prompt import Event
from flycast.react import demo_brain, react


def test_react_miss_returns_picked():
    brain, tok = demo_brain()
    result = react(brain, tok, [Event("MISS", "green")])
    assert result.mode == "picked"
    assert result.text
