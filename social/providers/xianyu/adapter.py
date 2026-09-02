from __future__ import annotations

import os
from typing import Any

from integrations.contracts.distribution import CapabilityRecord
from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.auth.credentials import CredentialRecord
from social.media_policy import validate_job
from social.providers.base import BaseCNAdapter
from social.providers.errors import AuthenticationError, CapabilityUnsupported, PolicyBlocked, PublishError, ValidationError
from social.providers.xianyu.auth import XianyuAuth
from social.providers.xianyu.capabilities import CLAIMED
from social.providers.xianyu.client import XianyuClient
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
                status="AUTHENTICATED",
                region="cn",
                capabilities=SocialProviderCapabilities.from_claimed(CLAIMED),
                provider_account_id=uid,
                credential_ref=getattr(self, "_credential_ref", "") or "",
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
        token = str(creds.get("access_token") or "")
        jushita = self.jushita_ready()
        method = "runtime_probe" if jushita and token else "jushita_required"
        records = {
            name: CapabilityRecord(name=name, supported=bool(value), verified=bool(value and jushita and token), method=method)
            for name, value in CLAIMED.items()
        }
        if not jushita:
            for name in ("listing", "listing_edit", "listing_delete", "media_upload"):
                records[name] = CapabilityRecord(name=name, supported=True, verified=False, method="jushita_required")
        return SocialProviderCapabilities.from_records(records)

    def _validate_platform(self, job, account) -> list[str]:
        errors = validate_job(job, platform="xianyu")
        if not self.jushita_ready():
            errors.append("xianyu production listing requires deployment_mode=JUSHITA")
        return errors

    def publish(self, job) -> dict[str, Any]:
        if not self.jushita_ready():
            raise CapabilityUnsupported("Xianyu listing publish is BLOCKED until deployment_mode=JUSHITA")
        listing = (job.variant.metadata or {}).get("listing") or {}
        if (job.variant.metadata or {}).get("commerce_intent", listing.get("commerce_intent") or "none") in {"", "none"} and not listing:
            raise PolicyBlocked("Xianyu listing requires explicit commerce intent")
        if not listing.get("title") or listing.get("price") in {None, ""} or not listing.get("category_id"):
            raise ValidationError("Xianyu listing requires title, price, and category_id")
        account = self.get_account(job.account_id)
        creds = self._credentials(account)
        token = str(creds.get("access_token") or "")
        uploaded = list((job.variant.metadata or {}).get("uploaded_media") or [])
        images = [str(item.get("remote_id") or item.get("remote_path") or "") for item in uploaded if item.get("remote_id") or item.get("remote_path")]
        payload = {
            "title": listing.get("title") or job.variant.title,
            "desc": listing.get("description") or job.variant.body,
            "price": str(listing.get("price")),
            "quantity": str(listing.get("quantity") or 1),
            "category_id": listing.get("category_id"),
            "images": ",".join(images),
        }
        result = self.xy_client.item_publish(token, payload, request_id=job.request_id, distribution_job_id=job.job_id, account_id=job.account_id, idempotency_key=job.idempotency_key or job.job_id)
        item = item_from_payload(result if isinstance(result, dict) else {})
        if not item.item_id:
            raise PublishError("Xianyu item.publish did not return item_id; success is not online")
        return {
            "id": item.item_id,
            "post_id": item.item_id,
            "external_id": item.item_id,
            "status": "processing",
            "provider_object_type": "listing",
        }

    def get_status(self, provider_post_id: str) -> dict[str, Any]:
        if not self.jushita_ready():
            return {"id": provider_post_id, "status": "unknown", "reason": "JUSHITA required", "provider_object_type": "listing"}
        creds = self._credentials()
        token = str(creds.get("access_token") or "")
        result = self.xy_client.item_query(token, provider_post_id)
        item = item_from_payload(result if isinstance(result, dict) else {})
        return {"id": item.item_id or provider_post_id, "status": map_status(item.status), "raw": result, "provider_object_type": "listing"}

    def analytics(self, publication) -> dict[str, Any | None]:
        try:
            raw = self.get_status(publication.provider_post_id)
        except Exception:
            return {"views": None, "likes": None, "comments": None, "shares": None, "followers_delta": None, "pv": None, "click": None, "inquiry": None, "order": None}
        data = raw.get("raw") if isinstance(raw.get("raw"), dict) else {}
        stats = data.get("data") if isinstance(data.get("data"), dict) else data
        return {
            "views": None,
            "likes": None,
            "comments": None,
            "shares": None,
            "followers_delta": None,
            "pv": stats.get("pv") if isinstance(stats, dict) else None,
            "click": stats.get("click") if isinstance(stats, dict) else None,
            "inquiry": (stats.get("consult") or stats.get("inquiry")) if isinstance(stats, dict) else None,
            "order": stats.get("order") if isinstance(stats, dict) else None,
            "listing_status": raw.get("status"),
        }
