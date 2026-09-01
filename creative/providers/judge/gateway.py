"""AI Gateway vision provider. Independent from Lechuang. Production never auto-PASS."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from creative.errors import JudgeBlocked, ProviderBlocked
from creative.schemas import Character, JudgeResult, MediaAsset, utcnow

PASS_SCORE = 70.0
JUDGE_SCHEMA = (
    '{"score":0-100,"passed":false,"reasons":[],"violations":[],"warnings":[],'
    '"breakdown":{"identity":0,"quality":0,"composition":0,"artifacts":0,"safety":0}}'
)


def _env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


class GatewayVisionProvider:
    name = "ai-gateway"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 45.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else _env("AI_GATEWAY_API_KEY", "VISION_API_KEY", "XIAOMI_API_KEY")
        self.base_url = (base_url if base_url is not None else _env("AI_GATEWAY_API_URL", "VISION_API_URL", "XIAOMI_BASE_URL")).rstrip("/")
        self.model = model if model is not None else (_env("AI_GATEWAY_VISION_MODEL", "VISION_MODEL") or "mimo-v2.5")
        self.timeout = timeout

    def live_ready(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "AI_GATEWAY_API_KEY missing"
        if not self.base_url:
            return False, "AI_GATEWAY_API_URL missing"
        return True, "ok"

    def probe(self) -> tuple[bool, str]:
        ready, reason = self.live_ready()
        if not ready:
            return False, reason
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Reply with JSON {\"ok\": true} only."}],
                "max_tokens": 32,
            }
            self._post("/chat/completions", payload)
            return True, "ok"
        except ProviderBlocked as exc:
            return False, str(exc)
        except Exception as exc:
            return False, f"AI Gateway unavailable: {exc}"

    def judge_image(self, asset: MediaAsset, *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult:
        return self._judge(asset, judge_type="image", brief=brief or {}, character=character, reference=reference)

    def judge_video(self, asset: MediaAsset, *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult:
        return self._judge(asset, judge_type="video", brief=brief or {}, character=character, reference=reference)

    def judge_frames(self, frames: list[str], *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult:
        existing = [item for item in frames if Path(item).is_file()]
        if not existing:
            raise JudgeBlocked("vision provider received no frames")
        fake = MediaAsset(asset_id="frames", type="image", path=existing[0], sha256="")
        return self._judge(fake, judge_type="video", brief=brief or {}, character=character, reference=reference, extra_paths=existing[1:3])

    def judge_consistency(self, assets: list[MediaAsset], *, brief: dict[str, Any] | None = None, character: Character | None = None, reference: MediaAsset | None = None) -> JudgeResult:
        if not assets:
            raise JudgeBlocked("vision provider received no assets")
        return self._judge(assets[0], judge_type="consistency", brief=brief or {}, character=character, reference=reference, extra_paths=[item.path for item in assets[1:3]])

    def _judge(
        self,
        asset: MediaAsset,
        *,
        judge_type: str,
        brief: dict[str, Any],
        character: Character | None,
        reference: MediaAsset | None,
        extra_paths: list[str] | None = None,
    ) -> JudgeResult:
        ready, reason = self.live_ready()
        if not ready:
            raise JudgeBlocked(reason)
        if asset is None or not asset.path or not Path(asset.path).is_file():
            raise JudgeBlocked("vision provider missing asset file")
        started = time.time()
        prompt = (
            "You are a visual QA judge. Inspect identity completeness, quality, composition, "
            "obvious generation errors, and content safety. Return JSON only matching "
            f"{JUDGE_SCHEMA}. Fail closed on missing limbs, identity mismatch, or unsafe content. "
            f"brief={json.dumps(brief, ensure_ascii=False)[:800]}"
        )
        if character is not None:
            prompt += f" character_id={character.character_id}"
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for path in [asset.path, *list(extra_paths or [])]:
            encoded = _data_url(path)
            if encoded:
                content.append({"type": "image_url", "image_url": {"url": encoded}})
        if reference is not None and reference.path:
            encoded = _data_url(reference.path)
            if encoded:
                content.append({"type": "image_url", "image_url": {"url": encoded}})
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 400,
        }
        raw = self._post("/chat/completions", payload)
        parsed = _parse_judge_payload(raw)
        latency = (time.time() - started) * 1000
        score = float(parsed.get("score") or 0)
        reasons = tuple(str(item) for item in (parsed.get("reasons") or []) if item)
        violations = tuple(str(item) for item in (parsed.get("violations") or []) if item)
        warnings = tuple(str(item) for item in (parsed.get("warnings") or []) if item)
        if violations:
            score = min(score, 40.0)
        decision = "PASS" if score >= PASS_SCORE and not violations and not any(item.startswith("fail:") for item in reasons) else "FAIL"
        breakdown = parsed.get("breakdown") if isinstance(parsed.get("breakdown"), dict) else {}
        return JudgeResult(
            score=round(score, 2),
            decision=decision,
            reasons=reasons,
            judge_type=judge_type,
            judge_model=self.model,
            judge_version="gateway-v1",
            breakdown={str(key): float(value or 0) for key, value in breakdown.items()},
            timestamp=utcnow(),
            asset_id=asset.asset_id,
            judge_id=uuid4().hex,
            judge_provider=self.name,
            passed=decision == "PASS",
            violations=violations,
            warnings=warnings,
            latency_ms=round(latency, 2),
            cost=None,
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else str(exc)
            if exc.code in {401, 403}:
                raise ProviderBlocked(self.name, "AI Gateway unauthorized: Invalid API Key") from exc
            if exc.code == 429:
                raise ProviderBlocked(self.name, "AI Gateway rate limited", details={"retryable": True}) from exc
            raise ProviderBlocked(self.name, f"AI Gateway HTTP {exc.code}: {body[:200]}", details={"retryable": exc.code >= 500}) from exc
        except TimeoutError as exc:
            raise ProviderBlocked(self.name, "AI Gateway timeout", details={"retryable": True}) from exc
        except URLError as exc:
            raise ProviderBlocked(self.name, f"AI Gateway unavailable: {exc.reason}", details={"retryable": True}) from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderBlocked(self.name, "AI Gateway invalid response") from exc
        if not isinstance(parsed, dict):
            raise ProviderBlocked(self.name, "AI Gateway invalid response")
        return parsed


def _data_url(path: str) -> str:
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    import base64
    payload = base64.b64encode(file_path.read_bytes()).decode("ascii")
    suffix = file_path.suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(suffix, "application/octet-stream")
    return f"data:{mime};base64,{payload}"


def _parse_judge_payload(raw: dict[str, Any]) -> dict[str, Any]:
    content = ""
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        content = str((message or {}).get("content") or "")
    if not content and isinstance(raw.get("score"), (int, float)):
        return raw
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JudgeBlocked("vision provider invalid response") from exc
    if not isinstance(parsed, dict) or "score" not in parsed:
        raise JudgeBlocked("vision provider invalid response")
    return parsed
