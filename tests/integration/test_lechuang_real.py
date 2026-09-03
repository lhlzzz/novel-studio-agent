"""Fail-closed Xiaole/Lechuang real-path tests. Skip is not E2E."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from creative.assets import MIN_PNG
from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.lechuang.adapter import LechuangAdapter
from creative.providers.lechuang.client import VIDEO_NOT_VERIFIED, LechuangClient, decode_image
from creative.providers.lechuang.credentials import API_KEY_ENV, load_creative_credential
from creative.providers.resolver import GenerationProviderResolver


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "docs/audits/meiti-v4.5.3-real-e2e.json"


def test_skip_is_not_real_e2e():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert audit["version"] == "4.5.3"
    assert audit["image"]["real_e2e"] is False or (
        audit["image"]["media_asset"] == "PASS" and audit["image"]["qa"] == "PASS"
    )
    if not load_creative_credential().present:
        assert audit["image"]["real_e2e"] is False
        assert audit["overall"] != "READY"


def test_real_image_e2e_fail_closed(tmp_path):
    cred = load_creative_credential()
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    if not cred.present:
        assert ready is False
        assert API_KEY_ENV in reason
        with pytest.raises(ProviderBlocked):
            adapter.generate_image({"prompt": "real image"})
        return
    assert ready is True
    if os.getenv("MEITI_PRODUCTION_E2E", "").strip().lower() != "true":
        with pytest.raises(UnsupportedCapability):
            adapter.generate_video({"prompt": "must not guess"})
        return
    live = LechuangAdapter(client=LechuangClient(asset_root=tmp_path))
    task = live.generate_image({"prompt": "one person one scene, fail-closed e2e"})
    assert task.status == "succeeded"
    asset = task.result["asset"]
    assert asset.asset_id
    assert asset.sha256
    assert Path(asset.path).is_file()
    assert Path(asset.path).stat().st_size > 0
    assert task.result["qa"]["decision"] == "pass"


def test_video_real_e2e_is_not_verified():
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))
    with pytest.raises(UnsupportedCapability):
        adapter.generate_video({"prompt": "must not guess"})
    status = adapter.capability_status("text_to_video")
    assert status["status"] == "NOT_VERIFIED"
    assert VIDEO_NOT_VERIFIED in status["reason"]


def test_resolver_image_requirement_uses_unified_provider():
    resolver = GenerationProviderResolver(
        providers={"lechuang": LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))},
        allow_mock=False,
    )
    adapter, name = resolver.resolve("xiaole")
    assert name == "lechuang"
    assert adapter.name == "lechuang"
    chosen, model = resolver.select({"output_types": ["image"], "capability": "text_to_image"})
    assert chosen.name == "lechuang"
    assert model is None or model.verified is True


def test_decode_image_rejects_non_image():
    import base64
    with pytest.raises(ProviderBlocked):
        decode_image("not-base64!!!")
    with pytest.raises(ProviderBlocked):
        decode_image(base64.b64encode(b"hello").decode("ascii"))
    encoded = base64.b64encode(MIN_PNG).decode("ascii")
    data, suffix = decode_image(encoded)
    assert data == MIN_PNG
    assert suffix == ".png"
