"""Unified Xiaole / Lechuang creative provider. Official image and video HTTP contract."""

from __future__ import annotations

from typing import Any

from creative.errors import ProviderBlocked, UnsupportedCapability
from creative.providers.base import CapabilityMixin
from creative.providers.lechuang.capabilities import claimed_capabilities, load_models
from creative.providers.lechuang.client import IMAGE_CONTRACT_VERIFIED, IMAGE_KINDS, VIDEO_CONTRACT_VERIFIED, VIDEO_KINDS, VIDEO_NOT_VERIFIED, LechuangClient
from creative.providers.lechuang.credentials import API_KEY_ENV
from creative.schemas import ProviderQuote, ProviderTask
from integrations.contracts.creative import CreativeArtifact

METHOD_TO_CAPABILITY = {
    "generate_text": "text_to_text",
    "generate_image": "text_to_image",
    "edit_image": "image_to_image",
    "generate_video": "text_to_video",
    "extend_video": "video_extend",
    "edit_video": "video_edit",
    "upload_asset": "upload_asset",
    "image_to_video": "image_to_video",
}

VERIFIED_CAPABILITIES = frozenset({"text_to_image", "image_generation", "generate_image"})
VIDEO_CAPABILITIES = frozenset({"text_to_video", "image_to_video", "video_generation", "generate_video"})
CLAIMED_UNVERIFIED = frozenset({
    "image_to_image",
    "video_extend",
    "video_edit",
    "upload_asset",
})


class LechuangAdapter(CapabilityMixin):
    name = "lechuang"

    def __init__(self, client: LechuangClient | None = None) -> None:
        self.client = client or LechuangClient()
        claimed = {item.name for item in claimed_capabilities()}
        self.supported = frozenset(claimed | VERIFIED_CAPABILITIES)
        self.verified_capabilities = frozenset(
            item.name for item in claimed_capabilities() if item.verified
        ) | VERIFIED_CAPABILITIES

    def live_ready(self) -> tuple[bool, str]:
        return self.client.live_ready()

    def authenticate(self) -> bool:
        return self.live_ready()[0]

    def has_verified(self, capability: str) -> bool:
        return capability in self.verified_capabilities

    def estimate(self, kind: str, payload: dict[str, Any] | None = None) -> float:
        quote = self.quote(kind, payload)
        return float(quote.credits)

    def quote(self, kind: str, payload: dict[str, Any] | None = None) -> ProviderQuote:
        models = load_models()
        credits = 1.0 if "image" in kind or kind in IMAGE_KINDS else 8.0
        for spec in (models.get("models") or {}).values():
            if kind in (spec.get("capabilities") or []) or METHOD_TO_CAPABILITY.get(kind) in (spec.get("capabilities") or []):
                credits = float(spec.get("cost_credits") or credits)
                break
        return ProviderQuote(credits=credits, mock=False, provider=self.name, parameters={"kind": kind, "source": "xiaole-lechuang"})

    def _require_verified(self, method: str) -> None:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("lechuang", reason)
        capability = METHOD_TO_CAPABILITY.get(method, method)
        if method in IMAGE_KINDS or capability in VERIFIED_CAPABILITIES:
            return
        if method in VIDEO_KINDS or capability in VIDEO_CAPABILITIES:
            return
        if capability in CLAIMED_UNVERIFIED or method in CLAIMED_UNVERIFIED:
            raise UnsupportedCapability(capability, provider="lechuang")
        raise UnsupportedCapability(capability, provider="lechuang")

    def create_task(self, kind: str, payload: dict[str, Any]) -> ProviderTask:
        self._require_verified(kind)
        return self.client.create_task(kind, payload)

    def get_task(self, provider_task_id: str) -> ProviderTask:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("lechuang", reason)
        return self.client.get_task(provider_task_id)

    def cancel_task(self, provider_task_id: str) -> ProviderTask:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("lechuang", reason)
        return self.client.cancel_task(provider_task_id)

    def get_result(self, provider_task_id: str) -> dict[str, Any]:
        ready, reason = self.live_ready()
        if not ready:
            raise ProviderBlocked("lechuang", reason)
        return self.client.get_result(provider_task_id)

    def generate_text(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("generate_text", provider="lechuang")

    def generate_image(self, payload: dict[str, Any]) -> ProviderTask:
        return self.create_task("generate_image", payload)

    def edit_image(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("image_to_image", provider="lechuang")

    def generate_video(self, payload: dict[str, Any]) -> ProviderTask:
        kind = str((payload or {}).get("kind") or (payload or {}).get("generation_type") or "generate_video")
        if kind in {"image_to_video", "IMAGE_TO_VIDEO"}:
            return self.create_task("image_to_video", payload)
        return self.create_task("generate_video", payload)

    def extend_video(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("video_extend", provider="lechuang")

    def edit_video(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("video_edit", provider="lechuang")

    def upload_asset(self, payload: dict[str, Any]) -> ProviderTask:
        raise UnsupportedCapability("upload_asset", provider="lechuang")

    def download_artifact(self, task: ProviderTask) -> CreativeArtifact:
        result = dict(task.result or {})
        asset = result.get("asset")
        path = str(getattr(asset, "path", None) or result.get("path") or "")
        sha256 = str(getattr(asset, "sha256", None) or result.get("sha256") or "")
        if not path or not sha256:
            raise ProviderBlocked("lechuang", "artifact path/sha256 missing")
        return CreativeArtifact(
            provider_artifact_id=str(result.get("provider_artifact_id") or task.provider_task_id or ""),
            source_url=str(result.get("source_url") or ""),
            path=path,
            sha256=sha256,
            mime_type=str(getattr(asset, "mime_type", None) or result.get("mime_type") or ""),
            byte_size=int(getattr(asset, "size", None) or result.get("byte_size") or 0),
            width=getattr(asset, "width", None) if asset is not None else result.get("width"),
            height=getattr(asset, "height", None) if asset is not None else result.get("height"),
            duration=getattr(asset, "duration", None) if asset is not None else result.get("duration"),
            asset_id=str(getattr(asset, "asset_id", None) or result.get("asset_id") or "") or None,
        )

    def verify(self, *, live: bool = False) -> dict[str, Any]:
        ready, reason = self.live_ready()
        configured = bool(self.client.credential.present)
        image_status = "VERIFIED" if IMAGE_CONTRACT_VERIFIED and ready else ("CONFIGURED" if configured else "BLOCKED")
        if configured and not ready:
            image_status = "BLOCKED"
        if not IMAGE_CONTRACT_VERIFIED:
            image_status = "UNVERIFIED"
        payload = {
            "LECHUANG_API_CONFIGURED": "PASS" if configured else "BLOCKED",
            "LECHUANG_API_REACHABLE": "UNVERIFIED" if not live else ("PASS" if ready else "BLOCKED"),
            "LECHUANG_IMAGE_CAPABILITY_VERIFIED": "VERIFIED" if IMAGE_CONTRACT_VERIFIED else "NOT_VERIFIED",
            "LECHUANG_VIDEO_CAPABILITY_VERIFIED": "VERIFIED" if VIDEO_CONTRACT_VERIFIED else "NOT_VERIFIED",
            "status": "VERIFIED" if ready and IMAGE_CONTRACT_VERIFIED else image_status,
            "reason": reason,
            "live": bool(live),
        }
        if live and ready:
            try:
                task = self.generate_image({
                    "prompt": "Meiti live doctor probe: one empty room, no text, no watermark.",
                    "model": "gpt-image-2",
                    "image_size": "512",
                    "aspect_ratio": "1:1",
                    "n": 1,
                    "idempotency_key": "lechuang-doctor-live-image",
                })
                artifact = self.download_artifact(task)
                payload["LECHUANG_API_REACHABLE"] = "PASS"
                payload["live_image"] = {
                    "status": task.status,
                    "provider_task_id": task.provider_task_id,
                    "sha256": artifact.sha256,
                    "path": artifact.path,
                }
            except Exception as exc:
                payload["LECHUANG_API_REACHABLE"] = "ERROR"
                payload["status"] = "ERROR"
                payload["reason"] = str(exc)
        return payload

    def capability_status(self, name: str) -> dict[str, Any]:
        ready, reason = self.live_ready()
        verified = self.has_verified(name)
        if name in {"video_extend", "video_edit"}:
            return {
                "status": "NOT_VERIFIED",
                "capability": name,
                "verified": False,
                "reason": "XiaoleAI video extend/edit is not present in official docs",
                "env": API_KEY_ENV,
            }
        if name in VIDEO_CAPABILITIES:
            if VIDEO_CONTRACT_VERIFIED and ready:
                return {"status": "PASS", "capability": name, "verified": True, "reason": reason, "env": API_KEY_ENV}
            if ready:
                return {
                    "status": "CONFIGURED",
                    "capability": name,
                    "verified": False,
                    "reason": VIDEO_NOT_VERIFIED,
                    "env": API_KEY_ENV,
                    "contract": "DOCUMENTED",
                }
            return {
                "status": "NOT_VERIFIED",
                "capability": name,
                "verified": False,
                "reason": VIDEO_NOT_VERIFIED,
                "env": API_KEY_ENV,
                "contract": "DOCUMENTED",
            }
        if name in {"image_to_image", "edit_image"}:
            return {
                "status": "NOT_VERIFIED",
                "capability": name,
                "verified": False,
                "reason": "XiaoleAI image editing is not present in repository evidence",
                "env": API_KEY_ENV,
            }
        if ready and verified:
            return {"status": "PASS", "capability": name, "verified": True, "reason": reason, "env": API_KEY_ENV}
        return {"status": "BLOCKED_EXTERNAL", "capability": name, "verified": verified, "reason": reason, "env": API_KEY_ENV}
