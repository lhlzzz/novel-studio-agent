"""Unified Xiaole/Lechuang credential, contract, MediaAsset, and CLI tests."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from creative.assets import MIN_PNG, persist_bytes
from creative.errors import AuthError, ProviderBlocked, RateLimited, UnsupportedCapability
from creative.judges.technical import TechnicalQA
from creative.providers.lechuang.adapter import LechuangAdapter
from creative.providers.lechuang.client import (
    IMAGE_ENDPOINT,
    VIDEO_NOT_VERIFIED,
    LechuangClient,
    decode_image,
    inspect_image_bytes,
)
from creative.providers.lechuang.credentials import (
    API_KEY_ENV,
    BASE_URL_ENV,
    DEFAULT_BASE_URL,
    load_creative_credential,
)
from creative.providers.resolver import GenerationProviderResolver


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._raw = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _png_b64() -> str:
    return base64.b64encode(MIN_PNG).decode("ascii")


def test_credential_loader_ignores_lechuang_env(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.delenv(BASE_URL_ENV, raising=False)
    monkeypatch.delenv("MEITI_SECRET_DIR", raising=False)
    monkeypatch.setenv("LECHUANG_API_KEY", "must-not-be-used")
    monkeypatch.setenv("LECHUANG_API_URL", "https://example.invalid")
    cred = load_creative_credential()
    assert cred.present is False
    assert cred.endpoint == DEFAULT_BASE_URL
    assert cred.provider == "xiaole"
    assert cred.service == "lechuang"


def test_credential_loader_uses_xiaole_env(monkeypatch):
    monkeypatch.delenv("MEITI_SECRET_DIR", raising=False)
    monkeypatch.setenv(API_KEY_ENV, "xiaole-secret")
    monkeypatch.setenv(BASE_URL_ENV, "https://api.xiaoleai.team/v1")
    cred = load_creative_credential()
    assert cred.present is True
    assert cred.source == "env"
    assert cred.endpoint == "https://api.xiaoleai.team/v1"


def test_decode_and_inspect_png():
    encoded = _png_b64()
    image_bytes, suffix = decode_image(encoded)
    assert suffix == ".png"
    width, height, mime = inspect_image_bytes(image_bytes)
    assert width == 1 and height == 1
    assert mime == "image/png"


def test_generate_image_persists_media_asset(tmp_path, monkeypatch):
    client = LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret", asset_root=tmp_path)

    def fake_urlopen(request, timeout=None):
        assert request.full_url.endswith(IMAGE_ENDPOINT)
        assert request.get_method() == "POST"
        body = json.loads(request.data.decode("utf-8"))
        assert body["response_format"] == "b64_json"
        assert body["model"] == "gpt-image-2"
        return _FakeResponse({"data": [{"b64_json": _png_b64()}], "id": "req-1", "model": "gpt-image-2"})

    monkeypatch.setattr("creative.providers.lechuang.client.urlopen", fake_urlopen)
    task = client.generate_image({"prompt": "one person one scene", "idempotency_key": "k1"})
    assert task.status == "succeeded"
    asset = task.result["asset"]
    assert Path(asset.path).is_file()
    assert Path(asset.path).stat().st_size > 0
    assert asset.sha256
    assert asset.mime_type == "image/png"
    assert task.result["qa"]["decision"] == "pass"
    again = client.generate_image({"prompt": "one person one scene", "idempotency_key": "k1"})
    assert again.provider_task_id == task.provider_task_id
    polled = client.get_task(task.provider_task_id)
    assert polled.status == "succeeded"
    result = client.get_result(task.provider_task_id)
    assert result["asset_id"] == asset.asset_id


def test_http_200_without_b64_is_failure(tmp_path, monkeypatch):
    client = LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret", asset_root=tmp_path)

    def fake_urlopen(request, timeout=None):
        return _FakeResponse({"data": [{"url": "https://example.invalid/image.png"}]})

    monkeypatch.setattr("creative.providers.lechuang.client.urlopen", fake_urlopen)
    with pytest.raises(ProviderBlocked):
        client.generate_image({"prompt": "x"})


def test_auth_rate_limit_timeout(monkeypatch):
    client = LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret")
    with pytest.raises(AuthError):
        client.map_http_error(401, "{}")
    with pytest.raises(RateLimited):
        client.handle_rate_limit(429, {"Retry-After": "2"})

    def boom(request, timeout=None):
        raise TimeoutError("slow")

    monkeypatch.setattr("creative.providers.lechuang.client.urlopen", boom)
    with pytest.raises(ProviderBlocked) as exc:
        client.generate_image({"prompt": "x"})
    assert "timeout" in str(exc.value).lower()


def test_video_and_image_edit_stay_not_verified():
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))
    for method in ("generate_video", "edit_image", "extend_video", "edit_video", "upload_asset"):
        with pytest.raises(UnsupportedCapability):
            getattr(adapter, method)({"prompt": "x"})
    assert adapter.capability_status("image_to_video")["status"] == "NOT_VERIFIED"
    assert VIDEO_NOT_VERIFIED in adapter.capability_status("text_to_video")["reason"]


def test_resolver_aliases_share_one_provider():
    adapter = LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))
    resolver = GenerationProviderResolver(providers={"lechuang": adapter}, allow_mock=False)
    for name in ("lechuang", "xiaole", "xiaoleai"):
        resolved, resolved_name = resolver.resolve(name)
        assert resolved_name == "lechuang"
        assert resolved is adapter
    assert "mock" not in resolver.providers


def test_technical_qa_on_persisted_png(tmp_path):
    asset = persist_bytes(MIN_PNG, asset_type="image", suffix=".png", root=tmp_path, mime_type="image/png", width=1, height=1)
    qa = TechnicalQA().inspect_image(asset)
    assert qa["decision"] == "pass"
    assert asset.size > 0


def test_cli_generate_video_is_not_verified(capsys):
    from scripts.meiti import cmd_creative_generate_video
    class Args:
        prompt = "x"
    assert cmd_creative_generate_video(Args()) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "NOT_VERIFIED"
    assert payload["VIDEO_CONTRACT_VERIFIED"] is False
    assert payload["VIDEO_PRODUCTION_READY"] == "NOT_VERIFIED"


def test_skill_path_is_media_owner():
    root = Path(__file__).resolve().parents[2]
    skill = (root / ".agents/skills/media/xiaoleai-image-generation/SKILL.md").read_text(encoding="utf-8")
    owned = ".agents/skills/media/xiaoleai-image-generation/scripts/generate_image.py"
    stale = ".agents/skills/" + "xiaoleai-image-generation/"
    assert owned in skill
    assert stale not in skill
    hits = []
    needle = "agents/skills/" + "xiaoleai-image-generation"
    skip = {".git", ".venv", "__pycache__", ".understand-anything", "postgres-data", "media", "node_modules"}
    for folder in (root / ".agents", root / "creative", root / "scripts", root / "docs", root / "tests"):
        for path in folder.rglob("*"):
            if not path.is_file() or any(part in skip for part in path.parts):
                continue
            if path.suffix.lower() not in {".md", ".py", ".yaml", ".yml", ".json", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if needle in text and "xiaoleai-image-generation/" in text.replace("/media/", "/"):
                if path.name == "test_xiaole_lechuang.py":
                    continue
                hits.append(str(path.relative_to(root)))
    assert hits == []


def test_cli_generate_image_blocked_without_key(monkeypatch, capsys):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.delenv("MEITI_SECRET_DIR", raising=False)
    from scripts.meiti import cmd_creative_generate_image
    class Args:
        prompt = "x"
        model = "gpt-image-2"
        image_size = "2K"
        aspect_ratio = "9:16"
    code = cmd_creative_generate_image(Args())
    assert code == 1
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["status"] == "BLOCKED_EXTERNAL"


def test_audit_owner_is_v454():
    root = Path(__file__).resolve().parents[2]
    legacy = json.loads((root / "docs/audits/meiti-v4.5.3-real-e2e.json").read_text(encoding="utf-8"))
    assert legacy["version"] == "4.5.3"
    path = root / "docs/audits/meiti-v4.5.4-real-e2e.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == "4.5.4"
    assert data["provider"] == "xiaole-lechuang"
    assert data["video"]["contract"] == "NOT_VERIFIED"
    assert data["video"]["capability"] == "NOT_VERIFIED"
    assert data["image_to_video"]["real_e2e"] is False
    dumped = json.dumps(data).lower()
    assert "api_key" not in dumped
    assert "token" not in dumped
    assert "authorization" not in dumped


def test_creative_doctor_keeps_image_and_video_independent(monkeypatch):
    from scripts import creative_doctor

    monkeypatch.setattr(creative_doctor, "AUDIT_PATH", Path(__file__).resolve().parents[2] / "docs/audits/meiti-v4.5.4-real-e2e.json")
    checks = creative_doctor.run()
    assert checks["LIVE"]["VIDEO_PRODUCTION_READY"]["status"] == "NOT_VERIFIED"
    assert checks["LIVE"]["IMAGE_TO_VIDEO_PRODUCTION_READY"]["status"] == "NOT_VERIFIED"
    image = checks["LIVE"]["IMAGE_PRODUCTION_READY"]["status"]
    assert image in {"PASS", "BLOCKED_EXTERNAL"}
    creative = checks["LIVE"]["CREATIVE_PRODUCTION_READY"]["status"]
    if image == "PASS":
        assert creative == "PASS"
    else:
        assert creative == "BLOCKED_EXTERNAL"
