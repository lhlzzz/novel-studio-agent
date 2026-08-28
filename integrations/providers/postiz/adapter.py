"""Meiti provider adapter for the externally operated Postiz engine."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from integrations.contracts.distribution import (
    DistributionJob,
    Integration,
    IntegrationCapabilities,
    validate_common_payload,
)
from integrations.providers.postiz.client import PostizClient
from integrations.providers.postiz.schemas import unwrap_data


class PostizAdapter:
    """Map Meiti's provider-neutral contract to Postiz Public API calls."""

    provider = "postiz"

    def __init__(
        self,
        client: PostizClient | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.client = client or PostizClient(base_url=base_url, api_key=api_key)

    @property
    def base_url(self) -> str:
        return self.client.base_url

    @property
    def api_key(self) -> str:
        return self.client.api_key

    @staticmethod
    def _integration(item: dict[str, Any]) -> Integration:
        identifier = str(item.get("identifier") or item.get("provider") or "unknown")
        return Integration(
            id=str(item["id"]),
            provider=identifier,
            account_id=str(item.get("account_id") or item.get("name") or ""),
            region=str(item.get("region") or "global"),
            capabilities=IntegrationCapabilities(
                publish=True,
                schedule=True,
                analytics=True,
                media=True,
                media_upload=True,
            ),
            adapter="postiz",
            distribution_backend="postiz",
            enabled=True,
        )

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

    def get_settings(self, integration_id: str) -> dict[str, Any]:
        raw = self.client.get_integration_settings(integration_id)
        return raw if isinstance(raw, dict) else {"data": raw}

    def validate_payload(self, job: DistributionJob) -> list[str]:
        try:
            integration = self.get_integration(job.integration_id)
        except KeyError:
            return [f"unknown Postiz integration: {job.integration_id}"]
        return validate_common_payload(job, integration)

    def prepare_publish(self, job: DistributionJob) -> dict[str, Any]:
        errors = self.validate_payload(job)
        return {
            "status": "blocked" if errors else "prepared",
            "provider": self.provider,
            "errors": errors,
            "job": asdict(job),
        }

    def _payload(self, job: DistributionJob, *, post_type: str) -> dict[str, Any]:
        media = [
            {"id": uuid.uuid4().hex, "path": path}
            for path in job.variant.media
        ]
        settings = dict(job.variant.metadata.get("settings") or {})
        settings.setdefault("__type", self.get_integration(job.integration_id).provider)
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
                        {"content": job.variant.body, "image": media, "delay": 0}
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
        return result

    def publish(self, job: DistributionJob) -> dict[str, Any]:
        return self._post_response(self.client.create_post(self._payload(job, post_type="now")))

    def schedule(self, job: DistributionJob) -> dict[str, Any]:
        return self._post_response(self.client.create_post(self._payload(job, post_type="schedule")))

    def get_status(self, job_id: str) -> dict[str, Any]:
        raw = unwrap_data(self.client.list_posts())
        posts = raw if isinstance(raw, list) else []
        return next(
            (post for post in posts if str(post.get("id")) == job_id),
            {"id": job_id, "status": "missing"},
        )

    def delete(self, job_id: str) -> dict[str, Any]:
        raw = self.client.delete_post(job_id)
        return raw if isinstance(raw, dict) else {"data": raw}

    def get_analytics(self, job_id: str) -> dict[str, Any]:
        raw = self.client.get_post_analytics(job_id)
        return raw if isinstance(raw, dict) else {"data": raw}

    def upload(self, file_path: str) -> dict[str, Any]:
        raw = self.client.upload_media(file_path)
        return raw if isinstance(raw, dict) else {"data": raw}

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
