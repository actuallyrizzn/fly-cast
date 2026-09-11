"""CLI smoke."""

from __future__ import annotations

from pathlib import Path

from flycast.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_say_exits_zero():
    assert main(["say", "hello", "there"]) == 0


def test_pick_cli():
    assert main(["pick", "MISS", "Dropped that one.", "Nice catch."]) == 0


def test_replay_cli():
    assert main(["replay", str(ROOT / "fixtures" / "events_midtempo.jsonl")]) == 0


def test_guard_cli_ok(tmp_path: Path):
    assert (
        main(
            [
                "guard",
                "On",
                "time.",
                "--stop-path",
                str(tmp_path / "STOP"),
                "--line-log",
                str(tmp_path / "log.jsonl"),
            ]
        )
        == 0
    )


def test_guard_cli_blocks(tmp_path: Path):
    assert (
        main(
            [
                "guard",
                "consider",
                "suicide",
                "--stop-path",
                str(tmp_path / "STOP"),
            ]
        )
        == 1
    )


def test_replay_with_guard(tmp_path: Path):
    assert (
        main(
            [
                "replay",
                str(ROOT / "fixtures" / "events_midtempo.jsonl"),
                "--guard",
                "--stop-path",
                str(tmp_path / "STOP"),
                "--line-log",
                str(tmp_path / "lines.jsonl"),
            ]
        )
        == 0
    )
