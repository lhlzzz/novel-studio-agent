from creative.assets import MIN_PNG, persist_bytes, sha256_bytes


def test_same_bytes_same_identity(tmp_path):
    first = persist_bytes(MIN_PNG, asset_type="image", suffix=".png", root=tmp_path, mime_type="image/png", width=1, height=1)
    second = persist_bytes(MIN_PNG, asset_type="image", suffix=".png", root=tmp_path, mime_type="image/png", width=1, height=1)
    assert first.sha256 == second.sha256 == sha256_bytes(MIN_PNG)
    assert first.path == second.path
    assert (tmp_path / first.sha256[:2] / f"{first.sha256}.png").read_bytes() == MIN_PNG
