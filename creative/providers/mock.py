"""Deterministic generation backend for tests. Never reported as live Lechuang."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from creative.assets import AssetStore
from creative.errors import UnsupportedCapability
from creative.providers.base import CapabilityMixin
from creative.schemas import MediaAsset, ProviderQuote, ProviderTask, to_plain, utcnow

ALL_CAPABILITIES = frozenset({
    "generate_text",
    "generate_image",
    "edit_image",
    "generate_video",
    "extend_video",
    "edit_video",
    "upload_asset",
    "text_to_image",
    "image_to_image",
    "text_to_video",
    "image_to_video",
})


class MockGenerationProvider(CapabilityMixin):
    name = "mock"
    supported = ALL_CAPABILITIES
    verified_capabilities = ALL_CAPABILITIES

    def __init__(self, *, store: AssetStore | None = None, polls_until_done: int = 0, costs: dict[str, float] | None = None) -> None:
        self.store = store or AssetStore()
        self.polls_until_done = polls_until_done
        self.costs = costs or {
            "generate_image": 1.0,
            "edit_image": 1.0,
            "generate_video": 8.0,
            "extend_video": 6.0,
            "edit_video": 4.0,
            "generate_text": 0.1,
            "upload_asset": 0.0,
        }
        self.task_dir = Path(self.store.root) / "_mock_tasks"
        self.task_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, ProviderTask] = {}

    def has_verified(self, capability: str) -> bool:
        return capability in self.supported

    def estimate(self, kind: str, payload: dict[str, Any] | None = None) -> float:
        return float(self.costs.get(kind, 1.0))

    def quote(self, kind: str, payload: dict[str, Any] | None = None) -> ProviderQuote:
        return ProviderQuote(credits=self.estimate(kind, payload), mock=True, provider=self.name, parameters={"kind": kind})

    def create_task(self, kind: str, payload: dict[str, Any]) -> ProviderTask:
        if kind not in self.supported:
            raise UnsupportedCapability(kind, provider=self.name)
        key = str((payload or {}).get("idempotency_key") or "")
        if key:
            for task in self._tasks.values():
                stored = getattr(task, "result", {}) or {}
                if stored.get("idempotency_key") == key:
                    return task
            for path in self.task_dir.glob("*.json"):
                raw = json.loads(path.read_text())
                if (raw.get("payload") or {}).get("idempotency_key") == key:
                    task = raw.get("task") or {}
                    return ProviderTask(
                        provider=self.name,
                        provider_task_id=str(task.get("provider_task_id") or path.stem),
                        status=str(task.get("status") or "queued"),
                        kind=str(task.get("kind") or kind),
                        result=dict(task.get("result") or {}),
                    )
        task_id = uuid4().hex
        status = "succeeded" if self.polls_until_done <= 0 else "queued"
        result = self._result(kind, payload) if status == "succeeded" else {}
        if key:
            result = {**result, "idempotency_key": key}
        task = ProviderTask(provider=self.name, provider_task_id=task_id, status=status, kind=kind, result=result)
        self._save(task, payload)
        return task

    def get_task(self, provider_task_id: str) -> ProviderTask:
        task, payload = self._load(provider_task_id)
        poll = task.poll_count + 1
        if task.status in {"queued", "running"} and poll >= self.polls_until_done:
            result = self._result(task.kind, payload)
            task = ProviderTask(
                provider=self.name,
                provider_task_id=task.provider_task_id,
                status="succeeded",
                kind=task.kind,
                result=result,
                poll_count=poll,
            )
        else:
            task = ProviderTask(
                provider=task.provider,
                provider_task_id=task.provider_task_id,
                status="running" if task.status == "queued" else task.status,
                kind=task.kind,
                result=task.result,
                error=task.error,
                poll_count=poll,
            )
        self._save(task, payload)
        return task

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        task, payload = self._load(provider_task_id)
        task = ProviderTask(
            provider=self.name,
            provider_task_id=provider_task_id,
            status="cancelled",
            kind=task.kind,
            result=task.result,
            poll_count=task.poll_count,
        )
        self._save(task, payload)
        return task

    def get_result(self, provider_task_id: str) -> dict[str, Any]:
        task = self.get_task(provider_task_id)
        if task.status != "succeeded":
            return {"status": task.status, "error": task.error}
        return task.result

    def _path(self, task_id: str) -> Path:
        return self.task_dir / f"{task_id}.json"

    def _save(self, task: ProviderTask, payload: dict[str, Any]) -> None:
        self._tasks[task.provider_task_id] = task
        data = {
            "task": to_plain(task),
            "payload": to_plain(payload),
        }
        if isinstance(task.result.get("asset"), MediaAsset):
            data["task"]["result"]["asset"] = to_plain(task.result["asset"])
        self._path(task.provider_task_id).write_text(json.dumps(data, default=str), encoding="utf-8")

    def _load(self, task_id: str) -> tuple[ProviderTask, dict[str, Any]]:
        if task_id in self._tasks:
            payload = {}
            path = self._path(task_id)
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8")).get("payload") or {}
            return self._tasks[task_id], payload
        path = self._path(task_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data["task"]
        result = dict(raw.get("result") or {})
        asset = result.get("asset")
        if isinstance(asset, dict) and asset.get("sha256"):
            found = self.store.get(asset.get("asset_id")) or self.store.get(asset.get("sha256"))
            if found:
                result["asset"] = found
        task = ProviderTask(
            provider=raw.get("provider") or self.name,
            provider_task_id=raw["provider_task_id"],
            status=raw.get("status") or "queued",
            kind=raw.get("kind") or "",
            result=result,
            error=raw.get("error"),
            poll_count=int(raw.get("poll_count") or 0),
        )
        self._tasks[task_id] = task
        return task, dict(data.get("payload") or {})

    def _result(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id") or "")
        workflow_id = str(payload.get("workflow_id") or "")
        workflow_version = str(payload.get("workflow_version") or "")
        character_id = payload.get("character_id")
        if kind in {"generate_text"}:
            return {"text": str(payload.get("prompt") or "scene plan"), "created_at": utcnow()}
        width = int(payload.get("width") or 720)
        height = int(payload.get("height") or 1280)
        if kind in {"generate_image", "edit_image", "upload_asset"}:
            blob = _png_bytes(width, height, int(payload.get("variant_index") or 0), str(payload.get("prompt") or ""))
            asset = self.store.save_generated(
                blob,
                asset_type="image",
                suffix=".png",
                mime_type="image/png",
                width=width,
                height=height,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                creative_run_id=run_id,
                character_id=character_id,
                metadata={"kind": kind, "provider": self.name, "prompt": payload.get("prompt")},
            )
            return {"asset": asset, "credits_actual": self.costs.get(kind, 1.0)}
        duration = float(payload.get("duration_seconds") or 15)
        reference = payload.get("reference")
        video_bytes = _mp4_bytes(width, height, duration, str(payload.get("prompt") or ""), str(reference or ""), int(payload.get("variant_index") or 0))
        asset = self.store.save_generated(
            video_bytes,
            asset_type="video",
            suffix=".mp4",
            mime_type="video/mp4",
            width=width,
            height=height,
            duration=duration,
            fps=24,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            creative_run_id=run_id,
            character_id=character_id,
            metadata={"kind": kind, "provider": self.name, "prompt": payload.get("prompt"), "mode": payload.get("mode"), "reference": str(reference or "")},
        )
        return {"asset": asset, "credits_actual": self.costs.get(kind, 8.0)}


def _png_bytes(width: int, height: int, variant: int, prompt: str) -> bytes:
    from PIL import Image, ImageDraw
    color = ((40 + variant * 36) % 200 + 20, 90, 140)
    image = Image.new("RGB", (max(width, 2), max(height, 2)), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle([8, 8, image.size[0] - 8, image.size[1] - 8], outline=(255, 255, 255), width=6)
    draw.text((24, 24), (prompt or "mock")[:48], fill=(255, 255, 255))
    buf = __import__("io").BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _mp4_bytes(width: int, height: int, duration: float, prompt: str, reference: str, variant: int) -> bytes:
    from creative.render.ffmpeg import run_ffmpeg
    png = _png_bytes(width, height, variant, f"{prompt}:{reference}")
    with tempfile.TemporaryDirectory(prefix="meiti-mock-") as tmp:
        src = Path(tmp) / "frame.png"
        dest = Path(tmp) / "clip.mp4"
        src.write_bytes(png)
        run_ffmpeg([
            "-loop", "1", "-i", str(src),
            "-t", f"{max(duration, 0.2):.3f}",
            "-r", "24",
            "-vf", f"scale={width}:{height}",
            "-pix_fmt", "yuv420p",
            "-an",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            str(dest),
        ])
        return dest.read_bytes()
