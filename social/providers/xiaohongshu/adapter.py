from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from integrations.contracts.distribution import CapabilityRecord
from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.handoff.export import materialize_handoff_export
from social.handoff.models import XHSHandoff
from social.media_policy import validate_job
from social.providers.base import BaseCNAdapter
from social.providers.errors import CapabilityUnsupported, ValidationError
from social.providers.xiaohongshu.auth import XiaohongshuAuth
from social.providers.xiaohongshu.capabilities import CLAIMED
from social.providers.xiaohongshu.client import XiaohongshuClient
from social.providers.xiaohongshu.contract import DIRECT_PUBLISH_AVAILABLE, OAUTH_ARCHITECTURE_SUPPORTED, SHARE_IMAGE_MAX, SHARE_IMAGE_MIN, WRITE_NOTES_AVAILABLE
from social.providers.xiaohongshu.schemas import XHSNotePackage


def _utcnow() -> str:
    from datetime import datetime, timezone
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
        self.handoffs: dict[str, XHSHandoff] = {}

    def authenticate(self, authorization: dict[str, Any] | None = None) -> bool:
        authorization = authorization or {}
        if authorization.get("account_id") or authorization.get("username"):
            username = str(authorization.get("username") or "")
            account = SocialAccount(
                account_id=str(authorization.get("account_id") or f"xiaohongshu:{username}"),
                provider="xiaohongshu",
                platform="xiaohongshu",
                username=username,
                display_name=str(authorization.get("display_name") or username),
                status="HANDOFF_READY",
                region="cn",
                capabilities=self.verify_capabilities(""),
                provider_account_id=str(authorization.get("provider_account_id") or username),
            )
            self._accounts[account.account_id] = account
            return True
        return bool(self._accounts)

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        return list(self._accounts.values())

    def verify_capabilities(self, account_id: str) -> SocialProviderCapabilities:
        from integrations.contracts.distribution import make_capability
        now = _utcnow()
        records = dict(SocialProviderCapabilities.from_claimed(CLAIMED, verified=False).records)
        records["handoff"] = make_capability(
            "handoff",
            supported=True,
            authorized=True,
            contract_verified=True,
            live_verified=True,
            method="handoff_export",
            evidence={"surface": "client_share_sdk", "direct_publish": False, "verified_at": now},
            verified_at=now,
        )
        records["publish"] = CapabilityRecord(
            name="publish",
            supported=False,
            verified=False,
            authorized=False,
            contract_verified=False,
            live_verified=False,
            method="write_notes_unverified",
            evidence={"reason": "write_notes is not live-verified", "oauth_architecture": OAUTH_ARCHITECTURE_SUPPORTED, "write_notes": WRITE_NOTES_AVAILABLE},
        )
        records["direct_publish"] = CapabilityRecord(
            name="direct_publish",
            supported=bool(WRITE_NOTES_AVAILABLE and DIRECT_PUBLISH_AVAILABLE),
            verified=False,
            authorized=False,
            contract_verified=False,
            live_verified=False,
            method="write_notes_unverified",
            evidence={"reason": "direct note publish requires write_notes + official publish API", "oauth_architecture": OAUTH_ARCHITECTURE_SUPPORTED},
        )
        records["oauth"] = CapabilityRecord(
            name="oauth",
            supported=OAUTH_ARCHITECTURE_SUPPORTED,
            verified=False,
            authorized=False,
            contract_verified=False,
            live_verified=False,
            method="architecture_supported",
            evidence={"architecture_supported": True, "contract_verified": False},
        )
        records["image"] = CapabilityRecord(
            name="image",
            supported=True,
            verified=True,
            verified_at=now,
            method="platform_content_policy",
            evidence={"content_type": "image_note", "image_count": f"{SHARE_IMAGE_MIN}..{SHARE_IMAGE_MAX}"},
        )
        records["video"] = CapabilityRecord(
            name="video",
            supported=True,
            verified=True,
            verified_at=now,
            method="platform_content_policy",
            evidence={"content_type": "video_note", "video_count": 1, "cover": "0..1"},
        )
        return SocialProviderCapabilities.from_records(records)

    def _validate_platform(self, job, account) -> list[str]:
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

    def export_handoff(self, job) -> dict[str, Any]:
        return self.handoff_to_xhs(job)

    def handoff_to_xhs(self, job) -> dict[str, Any]:
        note = self.prepare_note(job)
        handoff_id = f"xhs-handoff-{job.job_id}"
        package = note.as_export()
        handoff = XHSHandoff(
            handoff_id=handoff_id,
            account_id=job.account_id,
            content_package_id=job.content_package_id,
            status="READY_FOR_XHS",
            export_path="",
            export_status="PENDING",
            content_type=note.content_type,
            title=note.title,
            content=note.content,
            hashtags=tuple(note.hashtags or ()),
            images=tuple(note.images or ()),
            video=note.video,
            cover=note.cover,
            distribution_job_id=job.job_id,
            package=package,
        )
        self.handoffs[handoff_id] = handoff
        return {
            "handoff_id": handoff_id,
            "kind": "handoff",
            "status": "READY_FOR_XHS",
            "export_path": "",
            "export_status": "PENDING",
            "created_at": handoff.created_at,
            "package": package,
            "content_type": note.content_type,
        }

    def publish_direct(self, job) -> dict[str, Any]:
        raise CapabilityUnsupported("Xiaohongshu publish_direct is BLOCKED until official server-side publish is verified")

    def ensure_media(self, job):
        # Official XHS is handoff-only. Local media paths stay in the export package.
        return job, []

    def publish(self, job) -> dict[str, Any]:
        if DIRECT_PUBLISH_AVAILABLE:
            return self.publish_direct(job)
        return self.handoff_to_xhs(job)

    def get_status(self, provider_post_id: str, *, account_id: str = "", provider_object_type: str = "") -> dict[str, Any]:
        raise CapabilityUnsupported("Xiaohongshu remote status is NOT_APPLICABLE; handoff is not a publication")

    def analytics(self, publication) -> dict[str, Any | None]:
        return {"views": None, "likes": None, "comments": None, "shares": None, "followers_delta": None}

    def refresh(self, account: SocialAccount) -> SocialAccount:
        raise CapabilityUnsupported("Xiaohongshu refresh is NOT_SUPPORTED")
