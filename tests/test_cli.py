"""CLI smoke."""

from __future__ import annotations

from flycast.cli import main


def test_say_exits_zero():
    assert main(["say", "hello", "there"]) == 0
