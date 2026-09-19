"""Import every jevlab module. Filled in by later cards."""


def test_jevlab_modules_import() -> None:
    import flycast.jevlab.arms
    import flycast.jevlab.data
    import flycast.jevlab.features
    import flycast.jevlab.latency
    import flycast.jevlab.readout
    import flycast.jevlab.reference
    import flycast.jevlab.scorer
    import flycast.jevlab.state
    import flycast.jevlab.vectors

    assert "load_split" in flycast.jevlab.data.__all__
    assert "smoke_root" in flycast.jevlab.data.__all__


def test_smoke_sst2_slice(smoke_task) -> None:
    assert len(smoke_task("sst2", "train")) == 400
    assert len(smoke_task("sst2", "valid")) == 50
    assert len(smoke_task("sst2", "test")) == 50
    assert len(smoke_task("clinc10", "train")) == 400
    assert len(smoke_task("bugsev", "test")) == 50

