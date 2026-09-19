"""state.write merges and stays readable if replace never happens."""

from flycast.jevlab.state import read, write


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
