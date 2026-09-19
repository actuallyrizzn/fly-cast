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

    assert flycast.jevlab.data.__all__ == []
