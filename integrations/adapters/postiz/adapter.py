"""Backward-compatible import for the single Postiz provider owner."""

from integrations.providers.postiz.adapter import PostizAdapter, PostizDistributionAdapter

__all__ = ["PostizAdapter", "PostizDistributionAdapter"]
