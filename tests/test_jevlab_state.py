"""state.write merges; frame without DISPLAY writes MISSING."""

from flycast.jevlab.state import frame, read, write


def test_write_merges_keys(tmp_path) -> None:
    write(tmp_path, task="sst2", phase="grid-1")
    write(tmp_path, progress={"done": 1, "total": 4})
    got = read(tmp_path)
    assert got["task"] == "sst2"
    assert got["progress"]["done"] == 1
    assert "updated" in got


def test_temp_without_replace_leaves_old(tmp_path) -> None:
    write(tmp_path, task="sst2", phase="grid-1")
    temp = tmp_path / "state.json.tmp"
    temp.write_text('{"broken": true}\n', encoding="utf-8")
    assert read(tmp_path)["task"] == "sst2"
    assert "broken" not in read(tmp_path)


def test_frame_without_display_writes_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    write(tmp_path, task="sst2", phase="seeds")
    path = frame(tmp_path, "seed0")
    assert path.name.startswith("MISSING_")
    assert path.exists()
    assert read(tmp_path).get("glass") is False
    index = (tmp_path / "frames" / "index.tsv").read_text(encoding="utf-8")
    assert "MISSING_seed0.txt" in index
    assert "seed0" in index
