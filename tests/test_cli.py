"""CLI smoke."""

from __future__ import annotations

from flycast.cli import main


def test_say_exits_zero():
    assert main(["say", "hello", "there"]) == 0


def test_pick_cli():
    assert main(["pick", "MISS", "Dropped that one.", "Nice catch."]) == 0
