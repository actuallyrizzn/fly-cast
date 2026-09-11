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


def test_overlay_set_and_serve_once(tmp_path: Path):
    state = tmp_path / "state.json"
    assert (
        main(
            [
                "overlay",
                "set",
                "--line",
                "That's a wrap.",
                "--mode",
                "picked",
                "--status",
                "live",
                "--cues",
                "SONG_END",
                "--state-path",
                str(state),
            ]
        )
        == 0
    )
    assert state.is_file()
    assert (
        main(
            [
                "overlay",
                "serve",
                "--state-path",
                str(state),
                "--port",
                "0",
                "--once",
            ]
        )
        == 0
    )
