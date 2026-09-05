# Integration Providers

Social execution backends live in `social/providers/` and are resolved by
`resolve_social_provider()`.

Creative execution backends live in `creative/providers/` and are resolved by
`resolve_creative_provider()`.

Do not mix the two. Creative never publishes. Social never generates media.
