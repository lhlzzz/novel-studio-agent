from __future__ import annotations

import os
from typing import Any

from integrations.contracts.distribution import make_capability
from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.auth.credentials import CredentialRecord
from social.media_policy import validate_job
from social.providers.base import BaseCNAdapter
from social.providers.errors import AuthenticationError, CapabilityUnsupported, PolicyBlocked, PublishError, ValidationError
from social.providers.xianyu.auth import XianyuAuth
from social.providers.xianyu.capabilities import CLAIMED
from social.providers.xianyu.client import XianyuClient
from social.providers.xianyu.contract import (
    CONTRACT_VERIFIED,
    MEDIA_UPLOAD_BYTES_CONTRACT_VERIFIED,
    METHODS,
    ROUTER,
)
from social.providers.xianyu.schemas import item_from_payload, map_status, user_from_payload


def deployment_mode() -> str:
    return (os.getenv("MEITI_XIANYU_DEPLOYMENT_MODE") or os.getenv("XIANYU_DEPLOYMENT_MODE") or "LOCAL").strip().upper()


class XianyuAdapter(BaseCNAdapter):
    provider = "xianyu"
    platform = "xianyu"
    api_base = "https://eco.taobao.com"
    claimed = CLAIMED

    def __init__(self, *, client: XianyuClient | None = None, secrets: Any | None = None) -> None:
        http = None if client is None else client.http
        super().__init__(client=http, secrets=secrets)
        self.xy_client = client or XianyuClient(http=self.client)
        self.auth = XianyuAuth(client=self.client)
        self.deployment_mode = deployment_mode()

    def jushita_ready(self) -> bool:
        return self.deployment_mode == "JUSHITA"

    def authenticate(self, authorization: dict[str, Any] | None = None) -> bool:
        authorization = authorization or {}
        if authorization.get("code"):
            record = self.auth.exchange_code(str(authorization["code"]))
            self._credential_ref = self.secrets.put(record)
            return True
        if authorization.get("access_token"):
            self._credential_ref = self.secrets.put(CredentialRecord.from_payload({**authorization, "provider": "xianyu"}))
            return True
        return super().authenticate(authorization)

    def _discover_accounts(self, creds: dict[str, Any]) -> list[SocialAccount]:
        token = str(creds.get("access_token") or "")
        if not token:
            raise AuthenticationError("Xianyu account discovery is BLOCKED: access token missing")
        if not self.jushita_ready():
            uid = str(creds.get("provider_account_id") or creds.get("uid") or "")
            if not uid:
                raise CapabilityUnsupported("Xianyu user.info requires JUSHITA deployment")
            return [SocialAccount(
                account_id=f"xianyu:{uid}",
                provider="xianyu",
                platform="xianyu",
                username=str(creds.get("nick") or uid),
                status="IDENTITY_UNVERIFIED",
                region="cn",
                capabilities=SocialProviderCapabilities.from_claimed(CLAIMED),
                provider_account_id=uid,
                credential_ref=getattr(self, "_credential_ref", "") or "",
                blocked_reason="JUSHITA required for identity verification",
            )]
        payload = self.xy_client.user_info(token)
        user = user_from_payload(payload if isinstance(payload, dict) else {})
        if not user.user_id:
            raise AuthenticationError("Xianyu user.info did not return user_id")
        return [SocialAccount(
            account_id=f"xianyu:{user.user_id}",
            provider="xianyu",
            platform="xianyu",
            username=user.nick,
            display_name=user.nick,
            status="AUTHENTICATED",
            region="cn",
            capabilities=SocialProviderCapabilities.from_claimed(CLAIMED),
            provider_account_id=user.user_id,
            credential_ref=getattr(self, "_credential_ref", "") or "",
        )]

    def verify_capabilities(self, account_id: str) -> SocialProviderCapabilities:
        account = self.get_account(account_id)
        creds = self._credentials(account)
        token = bool(str(creds.get("access_token") or ""))
        jushita = self.jushita_ready()
        authorized = bool(jushita and token)
        records = {}
        for name, value in CLAIMED.items():
            if name == "media_upload":
                records[name] = make_capability(
                    name,
                    supported=False,
                    authorized=False,
                    contract_verified=MEDIA_UPLOAD_BYTES_CONTRACT_VERIFIED,
                    live_verified=False,
                    method="unverified_bytes_contract",
                    evidence={"mode": "url", "method": METHODS["media_upload"], "reason": "local bytes upload is not contract-verified"},
                )
                continue
            listing_names = {"listing", "listing_edit", "listing_delete", "image"}
            records[name] = make_capability(
                name,
                supported=bool(value),
                authorized=authorized if name in listing_names or name == "analytics" else False,
                contract_verified=bool(value and CONTRACT_VERIFIED),
                live_verified=False,
                method="official_endpoint" if jushita and token else "jushita_required",
                evidence={"deployment_mode": self.deployment_mode, "jushita": jushita, "router": ROUTER, "method": METHODS.get("item_publish")},
            )
        return SocialProviderCapabilities.from_records(records)

    def _validate_platform(self, job, account) -> list[str]:
        errors = validate_job(job, platform="xianyu")
        if not self.jushita_ready():
            errors.append("xianyu production listing requires deployment_mode=JUSHITA")
        return errors

    def _upload_bytes(self, data: bytes, *, mime_type: str, filename: str, account_id: str, idempotency_key: str) -> dict[str, Any]:
        raise CapabilityUnsupported(
            "Xianyu local-bytes media upload is BLOCKED: official alibaba.idle.isv.media.upload is URL-based and bytes upload is not contract-verified"
        )

    def upload_media(self, source_path: str, *, account_id: str = "", idempotency_key: str = ""):
        if str(source_path).startswith("https://"):
            account = self.get_account(account_id) if account_id else None
            creds = self._credentials(account)
            token = str(creds.get("access_token") or "")
            if not token:
                raise AuthenticationError("Xianyu media upload is BLOCKED: access token missing")
            result = self.xy_client.media_upload(token, source_path, account_id=account_id, idempotency_key=idempotency_key)
            data = result if isinstance(result, dict) else {}
            media_id = str(data.get("media_id") or data.get("id") or ((data.get("data") or {}) if isinstance(data.get("data"), dict) else {}).get("media_id") or "")
            if not media_id:
                raise ValidationError("Xianyu media.upload did not return media_id")
            from integrations.contracts.distribution import MediaUploadResult
            from datetime import datetime, timezone
            return MediaUploadResult(
                source_hash=media_id,
                source_path=source_path,
                mime_type="image/*",
                size=0,
                provider="xianyu",
                remote_id=media_id,
                remote_path=media_id,
                uploaded_at=datetime.now(timezone.utc).isoformat(),
                account_id=account_id,
            )
        raise CapabilityUnsupported(
            "Xianyu local-bytes media upload is BLOCKED until a verified bytes contract exists"
        )

    def publish(self, job) -> dict[str, Any]:
        if not self.jushita_ready():
            raise CapabilityUnsupported("Xianyu listing publish is BLOCKED until deployment_mode=JUSHITA")
        from commerce.models import CommerceDecision
        listing = (job.variant.metadata or {}).get("listing") or {}
        intent = CommerceDecision(
            intent=str((job.variant.metadata or {}).get("commerce_intent") or listing.get("commerce_intent") or "none"),
            source="distribution_job",
        )
        if not intent.allows_listing():
            raise PolicyBlocked("Xianyu listing requires explicit commerce intent")
        title = str(listing.get("title") or job.variant.title or "")
        price = listing.get("price")
        category_id = str(listing.get("category_id") or "")
        quantity = listing.get("quantity") if listing.get("quantity") not in {None, ""} else 1
        if not title or price in {None, ""} or not category_id:
            raise ValidationError("Xianyu listing requires title, price, and category_id")
        try:
            if float(price) <= 0:
                raise ValidationError("Xianyu listing price must be > 0")
        except (TypeError, ValueError) as exc:
            raise ValidationError("Xianyu listing price must be > 0") from exc
        try:
            if int(quantity) < 1:
                raise ValidationError("Xianyu listing quantity must be >= 1")
        except (TypeError, ValueError) as exc:
            raise ValidationError("Xianyu listing quantity must be >= 1") from exc
        account = self.get_account(job.account_id)
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        from social.providers.base import job_uploaded_media
        uploaded = job_uploaded_media(job)
        images = [str(item.remote_id or item.provider_media_id or item.remote_path) for item in uploaded if item.remote_id or item.provider_media_id or item.remote_path]
        if not images:
            raise ValidationError("Xianyu listing requires uploaded remote media identifiers; local paths are blocked")
        if any(item.startswith("/") or item.startswith(".") for item in images):
            raise ValidationError("Xianyu listing images must be remote media identifiers")
        payload = {
            "title": title,
            "desc": listing.get("description") or job.variant.body,
            "price": str(price),
            "quantity": str(int(quantity)),
            "category_id": category_id,
            "images": ",".join(images),
        }
        result = self.xy_client.item_publish(
            token,
            payload,
            request_id=job.request_id,
            distribution_job_id=job.job_id,
            account_id=job.account_id,
            idempotency_key=job.idempotency_key or job.job_id,
        )
        item = item_from_payload(result if isinstance(result, dict) else {})
        if not item.item_id:
            raise PublishError("Xianyu item.publish did not return item_id; success is not online")
        return {
            "kind": "listing",
            "provider_object_id": item.item_id,
            "item_id": item.item_id,
            "provider_request_id": str((result or {}).get("request_id") or "") or None,
            "external_id": item.item_id,
            "status": "processing",
            "provider_object_type": "listing",
            "listing": {
                "title": payload["title"],
                "description": str(payload.get("desc") or ""),
                "price": payload["price"],
                "quantity": int(payload["quantity"]),
                "category_id": payload["category_id"],
                "images": images,
                "condition": str(listing.get("condition") or "new"),
                "location": str(listing.get("location") or ""),
                "shipping": dict(listing.get("shipping") or {}),
                "attributes": dict(listing.get("attributes") or {}),
                "commerce_intent": "explicit",
                "content_package_id": job.content_package_id,
            },
        }

    def get_status(self, provider_post_id: str, *, account_id: str = "", provider_object_type: str = "listing") -> dict[str, Any]:
        if provider_object_type and provider_object_type != "listing":
            return {"id": provider_post_id, "status": "NOT_APPLICABLE", "provider_object_type": provider_object_type}
        if not self.jushita_ready():
            return {"id": provider_post_id, "status": "unknown", "reason": "JUSHITA required", "provider_object_type": "listing"}
        account = self._require_account(account_id)
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        result = self.xy_client.item_query(token, provider_post_id, account_id=account_id)
        item = item_from_payload(result if isinstance(result, dict) else {})
        return {"id": item.item_id or provider_post_id, "status": map_status(item.status), "raw": result, "provider_object_type": "listing"}

    def analytics(self, publication) -> dict[str, Any | None]:
        from social.providers.xianyu.analytics import XianyuAnalyticsClient
        creds = self._credentials(self._require_account(getattr(publication, "account_id", "")))
        token = str(creds.get("access_token") or "")
        return XianyuAnalyticsClient(self.xy_client).fetch(token, publication.provider_post_id)
