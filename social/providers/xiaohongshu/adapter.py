from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.providers.base import BaseCNAdapter
from social.providers.errors import CapabilityUnsupported, ValidationError
from social.providers.xiaohongshu.auth import XiaohongshuAuth
from social.providers.xiaohongshu.capabilities import CLAIMED
from social.providers.xiaohongshu.client import XiaohongshuClient
from social.providers.xiaohongshu.contract import DIRECT_PUBLISH_AVAILABLE, SHARE_IMAGE_MAX, SHARE_IMAGE_MIN
from social.providers.xiaohongshu.schemas import XHSNotePackage


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class XiaohongshuAdapter(BaseCNAdapter):
    provider = "xiaohongshu"
    platform = "xiaohongshu"
    api_base = ""
    claimed = CLAIMED

    def __init__(self, *, client: XiaohongshuClient | None = None, secrets: Any | None = None) -> None:
        super().__init__(client=None, secrets=secrets)
        self.xhs_client = client or XiaohongshuClient()
        self.auth = XiaohongshuAuth()
        self.handoffs: dict[str, dict[str, Any]] = {}

    def authenticate(self, authorization: dict[str, Any] | None = None) -> bool:
        authorization = authorization or {}
        if authorization.get("account_id") or authorization.get("username"):
            account = SocialAccount(
                account_id=str(authorization.get("account_id") or f"xiaohongshu:{authorization.get('username')}"),
                provider="xiaohongshu",
                platform="xiaohongshu",
                username=str(authorization.get("username") or ""),
                display_name=str(authorization.get("display_name") or authorization.get("username") or ""),
                status="AUTHENTICATED",
                region="cn",
                capabilities=SocialProviderCapabilities.from_claimed(CLAIMED),
                provider_account_id=str(authorization.get("provider_account_id") or authorization.get("username") or ""),
            )
            self._accounts[account.account_id] = account
            return True
        return bool(self._accounts)

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        return list(self._accounts.values())

    def verify_capabilities(self, account_id: str) -> SocialProviderCapabilities:
        from integrations.contracts.distribution import CapabilityRecord

        records = dict(SocialProviderCapabilities.from_claimed(CLAIMED, verified=False).records)
        records["handoff"] = CapabilityRecord(name="handoff", supported=True, verified=True, method="handoff_export", verification_method="handoff_export")
        records["publish"] = CapabilityRecord(name="publish", supported=False, verified=False, method="official_server_unavailable")
        records["direct_publish"] = CapabilityRecord(name="direct_publish", supported=DIRECT_PUBLISH_AVAILABLE, verified=False, method="official_server_unavailable")
        records["image"] = CapabilityRecord(name="image", supported=True, verified=True, method="handoff_export")
        records["video"] = CapabilityRecord(name="video", supported=True, verified=True, method="handoff_export")
        return SocialProviderCapabilities.from_records(records)

    def _validate_platform(self, job, account) -> list[str]:
        from social.media_policy import validate_job
        errors = validate_job(job, platform="xiaohongshu")
        images = [path for path in job.variant.media if Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
        videos = [path for path in job.variant.media if Path(path).suffix.lower() in {".mp4", ".mov"}]
        if videos and images:
            errors.append("xiaohongshu note cannot mix image note and video note")
        if images and not (SHARE_IMAGE_MIN <= len(images) <= SHARE_IMAGE_MAX):
            errors.append(f"xiaohongshu image note requires {SHARE_IMAGE_MIN}..{SHARE_IMAGE_MAX} images")
        if videos and len(videos) != 1:
            errors.append("xiaohongshu video note requires exactly 1 video")
        if not images and not videos:
            errors.append("xiaohongshu note requires images or a video")
        return errors

    def prepare_note(self, job) -> XHSNotePackage:
        images = [path for path in job.variant.media if Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
        videos = [path for path in job.variant.media if Path(path).suffix.lower() in {".mp4", ".mov"}]
        content_type = "video_note" if videos else "image_note"
        cover = (job.variant.metadata or {}).get("cover")
        return XHSNotePackage(
            content_type=content_type,
            title=job.variant.title,
            content=job.variant.body or job.variant.caption,
            hashtags=list(job.variant.hashtags or ()),
            images=images,
            video=videos[0] if videos else None,
            cover=cover,
            metadata=dict(job.variant.metadata or {}),
        )

    def prepare_image_note(self, job) -> XHSNotePackage:
        note = self.prepare_note(job)
        if note.content_type != "image_note":
            raise ValidationError("not an image note")
        return note

    def prepare_video_note(self, job) -> XHSNotePackage:
        note = self.prepare_note(job)
        if note.content_type != "video_note":
            raise ValidationError("not a video note")
        return note

    def handoff_to_xhs(self, job) -> dict[str, Any]:
        note = self.prepare_note(job)
        handoff_id = f"xhs-handoff-{uuid4().hex[:12]}"
        payload = {
            "handoff_id": handoff_id,
            "status": "READY_FOR_XHS",
            "created_at": _utcnow(),
            "package": note.as_export(),
            "id": handoff_id,
            "post_id": handoff_id,
            "provider_object_type": "note",
        }
        root = os.getenv("MEITI_XHS_HANDOFF_DIR", "").strip()
        if root:
            directory = Path(root)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{handoff_id}.json").write_text(json.dumps(payload["package"], ensure_ascii=False, indent=2), encoding="utf-8")
        self.handoffs[handoff_id] = payload
        return payload

    def publish_direct(self, job) -> dict[str, Any]:
        raise CapabilityUnsupported("Xiaohongshu publish_direct is BLOCKED until official server-side publish is verified")

    def publish(self, job) -> dict[str, Any]:
        if DIRECT_PUBLISH_AVAILABLE:
            return self.publish_direct(job)
        return self.handoff_to_xhs(job)

    def get_status(self, provider_post_id: str) -> dict[str, Any]:
        payload = self.handoffs.get(provider_post_id)
        if payload is None:
            return {"id": provider_post_id, "status": "NOT_PUBLISHED", "provider_object_type": "note"}
        return {"id": provider_post_id, "status": "NOT_PUBLISHED", "handoff_status": payload.get("status"), "provider_object_type": "note"}

    def analytics(self, publication) -> dict[str, Any | None]:
        return {"views": None, "likes": None, "comments": None, "shares": None, "followers_delta": None}


XHSAdapter = XiaohongshuAdapter
