"""Lechuang is the only Creative Provider. Video stays NOT_VERIFIED."""

from __future__ import annotations

import json
from pathlib import Path

from content.compiler import PromptCompiler
from content.runtime import ContinuityRuntime
from creative.idempotency import IdempotencyKey
from creative.providers.lechuang.adapter import LechuangAdapter
from creative.providers.lechuang.client import LechuangClient
from integrations.contracts.creative import CREATIVE_TASK_STATES, CreativeGenerationRequest, map_creative_status
from integrations.providers.resolver import resolve_creative_provider, resolve_social_provider
from tests.unit.test_account_continuity import _seed_account


def test_creative_contract_and_resolver_are_separate_from_social():
    from creative.providers.resolver import GenerationProviderResolver

    seeded = LechuangAdapter(client=LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret"))
    adapter, name = GenerationProviderResolver(providers={"lechuang": seeded}, allow_mock=False).resolve("xiaole")
    assert name == "lechuang"
    assert adapter.name == "lechuang"
    request = CreativeGenerationRequest(
        creator_account_id="acc",
        episode_id="ep",
        platform="xiaohongshu",
        generation_type="image",
        model="gpt-image-2",
        prompt="one person one scene",
        aspect_ratio="3:4",
        resolution="2K",
    )
    payload = request.to_payload()
    assert payload["account_id"] == "acc"
    assert payload["image_size"] == "2K"
    assert map_creative_status("succeeded") == "SUCCEEDED"
    assert map_creative_status("submitted") == "SUBMITTED"
    assert "EXPIRED" in CREATIVE_TASK_STATES
    assert resolve_social_provider is not resolve_creative_provider


def test_prompt_compiler_emits_generation_request():
    runtime = ContinuityRuntime.testing()
    account = _seed_account(runtime, platform="xiaohongshu", name="gen", character="张满血", world="深圳认真生活", series="30天系列")
    planned = runtime.produce_today(account_id=account.account_id, request="深圳夜跑")
    prompt = planned["prompt"]
    request = PromptCompiler(runtime.store).to_generation_request(prompt, production_run_id="run-1")
    assert request.creator_account_id == account.account_id
    assert request.generation_type == "image"
    assert request.model == "gpt-image-2"
    assert request.platform == "xiaohongshu"
    assert prompt.lechuang_parameters["mode"] == "api"
    assert "mode=api" in prompt.copy_ready
    assert planned["job_status"] == "SUBMITTED"
    assert planned["creative_provider"] == "lechuang"
    run = runtime.store.get_production_run_by_job(planned["job_id"])
    assert run is not None
    assert run.creative_provider == "lechuang"
    assert run.creative_request_snapshot["prompt"]


def test_day2_continue_does_not_repeat_day1():
    runtime = ContinuityRuntime.testing()
    account = _seed_account(runtime, platform="xiaohongshu", name="days", character="张满血", world="深圳认真生活", series="30天系列")
    day1 = runtime.today(account_id=account.account_id, request="做一个深圳夜跑的小红书视频")
    day2 = runtime.continue_yesterday(account_id=account.account_id, request="继续昨天")
    assert day1["EPISODE"]["episode_id"] != day2["episode"].episode_id
    assert day1["PROMPT"]["prompt_id"] != day2["prompt"].prompt_id
    prompt1 = runtime.store.get_prompt(day1["PROMPT"]["prompt_id"])
    assert day2["prompt"].copy_ready != prompt1.copy_ready
    assert day2["prompt"].scene_prompt != prompt1.scene_prompt
    assert day1["CREATIVE_JOB"] != day2["job_id"]
    assert day1["CONNECTION"] == "NOT_CONNECTED"


def test_idempotent_creative_job_does_not_resubmit():
    runtime = ContinuityRuntime.testing()
    account = _seed_account(runtime, platform="xiaohongshu", name="idemp", character="张满血", world="深圳认真生活", series="30天系列")
    first = runtime.produce_today(account_id=account.account_id, request="晨跑")
    again = runtime.submit_generation(
        account_id=account.account_id,
        episode_id=first["episode"].episode_id,
        prompt=first["prompt"],
        request="晨跑",
    )
    assert again["job_id"] == first["job_id"]
    spec = {
        "kind": first["prompt"].kind,
        "model": first["prompt"].recommended_model,
        "image_size": first["prompt"].recommended_size,
        "aspect_ratio": first["prompt"].aspect_ratio,
        "duration": first["prompt"].duration,
        "negative_prompt": first["prompt"].negative_prompt,
        "source_asset_id": first["prompt"].source_asset_id,
    }
    assert again["job_id"] == IdempotencyKey.creative_job(account.account_id, first["episode"].episode_id, first["prompt"].prompt_id, spec)


def test_download_artifact_uses_local_bytes(tmp_path, monkeypatch):
    import base64
    from creative.assets import MIN_PNG

    client = LechuangClient(base_url="https://api.xiaoleai.team/v1", api_key="secret", asset_root=tmp_path)
    adapter = LechuangAdapter(client=client)

    class _FakeResponse:
        def __init__(self, payload):
            self._raw = json.dumps(payload).encode("utf-8")
            self.status = 200

        def read(self):
            return self._raw

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        return _FakeResponse({"data": [{"b64_json": base64.b64encode(MIN_PNG).decode("ascii")}], "id": "req-local", "model": "gpt-image-2"})

    monkeypatch.setattr("creative.providers.lechuang.client.urlopen", fake_urlopen)
    task = adapter.generate_image({"prompt": "one person one scene"})
    artifact = adapter.download_artifact(task)
    assert Path(artifact.path).is_file()
    assert artifact.sha256
    assert artifact.source_url == ""
    assert task.result["cost_status"] == "UNKNOWN"


def test_cli_exposes_creative_job_commands():
    cli = (Path(__file__).resolve().parents[2] / "scripts/meiti.py").read_text(encoding="utf-8")
    for token in ("cmd_creative_providers", "cmd_creative_models", "cmd_creative_generate", "cmd_creative_status", "cmd_creative_retry", "cmd_creative_cancel", "cmd_creator_today"):
        assert token in cli
    assert "LechuangAdapter(" not in cli
    assert "manual-lechuang" in cli
