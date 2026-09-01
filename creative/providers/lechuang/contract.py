"""Lechuang API contract status. Unverified contracts stay BLOCKED."""

from creative.providers.lechuang.client import CONTRACT_VERIFIED, LechuangClient


def contract_status(client: LechuangClient | None = None) -> dict:
    client = client or LechuangClient()
    ready, reason = client.live_ready()
    return {
        "verified": bool(client.contract_verified and CONTRACT_VERIFIED),
        "ready": ready,
        "reason": reason,
    }
