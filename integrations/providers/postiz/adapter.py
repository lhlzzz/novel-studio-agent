"""Meiti provider adapter for the externally operated Postiz engine."""

from __future__ import annotations

import hashlib
import mimetypes
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from integrations.contracts.distribution import (
    CapabilityRecord,
    DistributionJob,
    Integration,
    IntegrationCapabilities,
    MediaUploadResult,
    validate_common_payload,
)
from integrations.providers.postiz.client import PostizClient
from integrations.providers.postiz.errors import PostizClientError
from integrations.providers.postiz.schemas import unwrap_data

SUPPORTED_BY_IDENTIFIER = {
    "x": ("publish", "schedule", "analytics", "media", "media_upload"),
    "twitter": ("publish", "schedule", "analytics", "media", "media_upload"),
    "linkedin": ("publish", "schedule", "analytics", "media", "media_upload"),
    "instagram": ("publish", "schedule", "analytics", "media", "media_upload"),
    "youtube": ("publish", "schedule", "analytics", "media", "media_upload"),
    "tiktok": ("publish", "schedule", "analytics", "media", "media_upload"),
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class PostizAdapter:
    """Map Meiti's provider-neutral contract to Postiz Public API calls."""

    provider = "postiz"

    def __init__(
        self,
        client: PostizClient | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        *,
        media_cache: dict[str, MediaUploadResult] | None = None,
    ) -> None:
        self.client = client or PostizClient(base_url=base_url, api_key=api_key)
        self._capability_cache: dict[str, IntegrationCapabilities] = {}
        self._media_cache = media_cache if media_cache is not None else {}
        self._verified_ids: set[str] = set()

    @property
    def base_url(self) -> str:
        return self.client.base_url

    @property
    def api_key(self) -> str:
        return self.client.api_key

    def authenticate(self) -> bool:
        return bool(self.client.is_connected())

    def health(self):
        return self.client.health()

    def upload_media(self, source_path: str) -> MediaUploadResult:
        return self.upload_local_media(source_path)

    def cancel(self, provider_post_id: str) -> dict[str, Any]:
        return self.delete(provider_post_id)

    def _claimed(self, identifier: str) -> dict[str, CapabilityRecord]:
        names = SUPPORTED_BY_IDENTIFIER.get(identifier, ("publish", "schedule", "analytics", "media", "media_upload"))
        return {
            name: CapabilityRecord(name=name, supported=True, verified=False, method="identifier_claim")
            for name in names
        }

    def _integration(self, item: dict[str, Any]) -> Integration:
        identifier = str(item.get("identifier") or item.get("provider") or "unknown")
        integration_id = str(item["id"])
        records = self._claimed(identifier)
        cached = self._capability_cache.get(integration_id)
        if cached is not None:
            capabilities = cached
            enabled = integration_id in self._verified_ids
            state = "ENABLED" if enabled else "VERIFIED" if enabled else "AUTHENTICATED"
        else:
            capabilities = IntegrationCapabilities(records=records)
            enabled = False
            state = "AUTHENTICATED"
        return Integration(
            id=integration_id,
            provider=self.provider,
            account_id=str(item.get("account_id") or item.get("name") or ""),
            region=str(item.get("region") or "global"),
            capabilities=capabilities,
            adapter="postiz",
            distribution_backend="postiz",
            enabled=enabled,
            state="ENABLED" if enabled else state,
            account_name=str(item.get("name") or ""),
            platform=identifier,
        )

    @contextmanager
    def _request_context(self, request_id: str | None):
        context = getattr(self.client, "request_context", None)
        if callable(context):
            with context(request_id or ""):
                yield
        else:
            yield

    def list_integrations(self) -> list[Integration]:
        raw = unwrap_data(self.client.list_integrations())
        items = raw if isinstance(raw, list) else []
        return [
            self._integration(item)
            for item in items
            if isinstance(item, dict) and item.get("id")
        ]

    def get_integration(self, integration_id: str) -> Integration:
        for integration in self.list_integrations():
            if integration.id == integration_id:
                return integration
        raise KeyError(integration_id)

    def get_capabilities(self, integration_id: str) -> IntegrationCapabilities:
        return self.get_integration(integration_id).capabilities

    def verify_capabilities(self, integration_id: str) -> IntegrationCapabilities:
        connected = False
        is_connected = getattr(self.client, "is_connected", None)
        if callable(is_connected):
            connected = bool(is_connected())
        integration = self.get_integration(integration_id)
        settings = self.get_settings(integration_id)
        method = "runtime_test"
        if not connected:
            method = "unverified"
        records = {}
        claimed = integration.capabilities.records or self._claimed(integration.provider)
        now = _utcnow()
        for name, record in claimed.items():
            verified = bool(connected and isinstance(settings, dict))
            records[name] = CapabilityRecord(
                name=name,
                supported=record.supported,
                verified=verified,
                verified_at=now if verified else None,
                method=method if verified else "unverified",
                verification_method=method if verified else "unverified",
            )
        capabilities = IntegrationCapabilities(
            publish=records.get("publish", CapabilityRecord("publish")).allowed,
            schedule=records.get("schedule", CapabilityRecord("schedule")).allowed,
            analytics=records.get("analytics", CapabilityRecord("analytics")).allowed,
            media=records.get("media", CapabilityRecord("media")).allowed,
            media_upload=records.get("media_upload", CapabilityRecord("media_upload")).allowed,
            records=records,
        )
        if capabilities.publish:
            self._verified_ids.add(integration_id)
        self._capability_cache[integration_id] = capabilities
        return capabilities

    def get_settings(self, integration_id: str) -> dict[str, Any]:
        raw = self.client.get_integration_settings(integration_id)
        return raw if isinstance(raw, dict) else {"data": raw}

    def validate_payload(self, job: DistributionJob) -> list[str]:
        try:
            integration = self.get_integration(job.integration_id)
        except KeyError:
            return [f"unknown Postiz integration: {job.integration_id}"]
        errors = validate_common_payload(job, integration)
        if job.variant.media:
            for path in job.variant.media:
                uploaded = (job.variant.metadata or {}).get("uploaded_media") or []
                cached = path in self._media_cache or any(
                    item.get("source_path") == path or item.get("remote_path") == path or item.get("postiz_media_path") == path
                    for item in uploaded if isinstance(item, dict)
                )
                if Path(path).is_file():
                    continue
                if not cached:
                    errors.append(f"media is not uploaded: {path}")
        return errors

    def prepare_publish(self, job: DistributionJob) -> dict[str, Any]:
        errors = self.validate_payload(job)
        return {
            "status": "blocked" if errors else "prepared",
            "provider": self.provider,
            "errors": errors,
            "job": asdict(job),
        }

    def _file_identity(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def upload_local_media(self, source_path: str) -> MediaUploadResult:
        path = Path(source_path)
        if not path.is_file():
            raise PostizClientError(f"media file does not exist: {path}")
        sha256 = self._file_identity(path)
        cached = self._media_cache.get(sha256)
        if cached is not None and cached.status == "uploaded":
            return cached
        raw = unwrap_data(self.client.upload_media(path))
        payload = raw if isinstance(raw, dict) else {}
        result = MediaUploadResult(
            source_hash=sha256,
            source_path=str(path),
            mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            size=path.stat().st_size,
            provider=self.provider,
            remote_id=str(payload.get("id") or payload.get("media_id") or sha256),
            remote_path=str(payload.get("path") or payload.get("url") or ""),
            uploaded_at=_utcnow(),
            status="uploaded" if payload else "failed",
        )
        if result.status != "uploaded" or not result.remote_path:
            raise PostizClientError(f"Postiz upload did not return a media path for {path}")
        self._media_cache[sha256] = result
        self._media_cache[result.source_hash] = result
        self._media_cache[str(path)] = result
        return result

    def ensure_media(self, job: DistributionJob) -> tuple[DistributionJob, list[MediaUploadResult]]:
        uploaded: list[MediaUploadResult] = []
        existing = list((job.variant.metadata or {}).get("uploaded_media") or [])
        for item in existing:
            if isinstance(item, dict) and (item.get("remote_path") or item.get("postiz_media_path")):
                uploaded.append(MediaUploadResult(
                    source_hash=str(item.get("source_hash") or item.get("sha256") or ""),
                    source_path=str(item.get("source_path") or ""),
                    mime_type=str(item.get("mime_type") or "application/octet-stream"),
                    size=int(item.get("size") or 0),
                    provider=str(item.get("provider") or self.provider),
                    remote_id=str(item.get("remote_id") or item.get("postiz_media_id") or ""),
                    remote_path=str(item.get("remote_path") or item.get("postiz_media_path") or ""),
                    uploaded_at=str(item.get("uploaded_at") or _utcnow()),
                    status=str(item.get("status") or "uploaded"),
                ))
        for path in job.variant.media:
            if any(result.source_path == path or result.remote_path == path for result in uploaded):
                continue
            if Path(path).is_file():
                uploaded.append(self.upload_local_media(path))
            elif path in self._media_cache:
                uploaded.append(self._media_cache[path])
            else:
                raise PostizClientError(f"media must be uploaded before publish: {path}")
        metadata = dict(job.variant.metadata or {})
        metadata["uploaded_media"] = [asdict(item) for item in uploaded]
        variant = replace(job.variant, metadata=metadata)
        return replace(job, variant=variant), uploaded

    def _payload(self, job: DistributionJob, *, post_type: str) -> dict[str, Any]:
        job, uploaded = self.ensure_media(job)
        media = [
            {"id": item.remote_id, "path": item.remote_path}
            for item in uploaded
        ]
        settings = dict(job.variant.metadata.get("settings") or {})
        integration = self.get_integration(job.integration_id)
        settings.setdefault("__type", integration.platform or integration.provider)
        if job.variant.title:
            settings.setdefault("title", job.variant.title)
        body = job.variant.body
        if job.variant.hashtags:
            tags = " ".join(job.variant.hashtags)
            if tags not in body:
                body = f"{body}\n{tags}".strip()
        if job.variant.cta and job.variant.cta not in body:
            body = f"{body}\n{job.variant.cta}".strip()
        return {
            "type": post_type,
            "creationMethod": "API",
            "date": job.scheduled_at or datetime.now(timezone.utc).isoformat(),
            "shortLink": True,
            "tags": [],
            "posts": [
                {
                    "integration": {"id": job.integration_id},
                    "value": [
                        {"content": body, "image": media, "delay": 0}
                    ],
                    "settings": settings,
                }
            ],
        }

    @staticmethod
    def _post_response(raw: Any) -> dict[str, Any]:
        payload = unwrap_data(raw)
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        if not isinstance(payload, dict):
            return {"data": payload}
        result = dict(payload)
        if result.get("id") is None and result.get("postId") is not None:
            result["id"] = result["postId"]
        if result.get("external_id") is None and result.get("externalId") is not None:
            result["external_id"] = result["externalId"]
        return result

    def publish(self, job: DistributionJob) -> dict[str, Any]:
        with self._request_context(job.request_id):
            return self._post_response(self.client.create_post(self._payload(job, post_type="now")))

    def schedule(self, job: DistributionJob) -> dict[str, Any]:
        with self._request_context(job.request_id):
            return self._post_response(self.client.create_post(self._payload(job, post_type="schedule")))

    def get_status(self, provider_post_id: str) -> dict[str, Any]:
        get_status = getattr(self.client, "get_status", None)
        raw = get_status(provider_post_id) if callable(get_status) else self.client.list_posts()
        raw = unwrap_data(raw)
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list):
            return next((item for item in raw if str(item.get("id")) == str(provider_post_id)), {
                "id": provider_post_id,
                "status": "UNKNOWN",
            })
        return {"id": provider_post_id, "status": "UNKNOWN"}

    def delete(self, provider_post_id: str) -> dict[str, Any]:
        raw = self.client.delete_post(provider_post_id)
        return raw if isinstance(raw, dict) else {"data": raw}

    def get_analytics(self, provider_post_id: str) -> dict[str, Any]:
        raw = self.client.get_post_analytics(provider_post_id)
        return raw if isinstance(raw, dict) else {"data": raw}

    def upload(self, file_path: str) -> dict[str, Any]:
        return asdict(self.upload_local_media(file_path))

    def analytics_platform(self, integration_id: str, days: int = 30) -> dict[str, Any]:
        raw = self.client.get_integration_analytics(integration_id, days)
        return raw if isinstance(raw, dict) else {"data": raw}

    def analytics_post(self, post_id: str, days: int = 7) -> dict[str, Any]:
        raw = self.client.get_post_analytics(post_id, days)
        return raw if isinstance(raw, dict) else {"data": raw}

    def trigger_integration_tool(
        self,
        integration_id: str,
        method_name: str,
        data: dict[str, Any] | None = None,
    ) -> Any:
        return self.client.trigger_integration_tool(integration_id, method_name, data)


PostizDistributionAdapter = PostizAdapter
