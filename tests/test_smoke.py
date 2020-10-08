def test_smoke(invoke):
    assert invoke(["dis.dis"]).exit_code == 0
