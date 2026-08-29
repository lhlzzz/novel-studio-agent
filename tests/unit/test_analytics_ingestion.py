from analytics.normalizers.metrics import normalize_metrics


def test_analytics_normalizer_preserves_unknown_metrics_as_null():
    result = normalize_metrics("postiz-1", {"views": 4, "likes": 2})
    assert result.values["views"] == 4
    assert result.values["likes"] == 2
    assert result.values["comments"] is None
