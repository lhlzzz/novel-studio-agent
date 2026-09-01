from intelligence.router import route_research, select_skill


def test_research_unavailable_without_credential(monkeypatch):
    monkeypatch.delenv("SCRAPECREATORS_API_KEY", raising=False)
    result = route_research({"kind": "trend"})
    assert result["status"] == "unavailable"
    assert result["publishable"] is False if "publishable" in result else True
    assert result["claims"] == []
    assert result.get("artifact") is None
    assert result["status"] != "ready"


def test_research_skill_router_selects_outlier():
    assert select_skill({"kind": "outlier posts"}) == "outlier-post-finder"
    assert select_skill({"kind": "competitor"}) == "competitor-social-research"
