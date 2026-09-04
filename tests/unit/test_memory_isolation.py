from content.models import IsolationError
from memory.models import MemoryFact
from memory.retrieval import remember, retrieve
from memory.service import AmbiguousAccount, MemoryService


def test_account_memory_does_not_leak_across_accounts():
    service = MemoryService.testing()
    service.remember(title="Character A", content="account A character secret", scope_type="CHARACTER", account_id="acc-a", character_id="char-a")
    service.remember(title="World A", content="account A world secret", scope_type="WORLD", account_id="acc-a", world_id="world-a")
    service.remember(title="Series A", content="account A series secret", scope_type="SERIES", account_id="acc-a", series_id="series-a")
    service.remember(title="Episode A", content="account A episode secret", scope_type="EPISODE", account_id="acc-a", episode_id="ep-a")
    service.remember(title="Strategy A", content="account A strategy secret", scope_type="ACCOUNT", account_id="acc-a")
    service.remember(title="Publication A", content="account A publication secret", scope_type="PUBLICATION", account_id="acc-a", publication_id="pub-a")
    service.remember(title="Analytics A", content="account A analytics secret", scope_type="ANALYTICS", account_id="acc-a")
    service.remember(title="Character B", content="account B character secret", scope_type="CHARACTER", account_id="acc-b", character_id="char-b")
    retrieved = service.retrieve({"query": "secret", "account_id": "acc-b"})
    docs = retrieved["documents"]
    leaked = [item for item in docs if item.account_id == "acc-a"]
    owned = [item for item in docs if item.account_id == "acc-b"]
    assert owned
    assert leaked == []
    titles = {item.title for item in docs}
    assert "Character A" not in titles
    assert "World A" not in titles
    assert "Series A" not in titles
    assert "Episode A" not in titles
    assert "Strategy A" not in titles
    assert "Publication A" not in titles
    assert "Analytics A" not in titles


def test_global_knowledge_is_visible_and_unscoped_memory_is_rejected():
    service = MemoryService.testing()
    global_doc = service.remember(title="Global Pattern", content="shared successful pattern", scope_type="GLOBAL", source_type="research")
    retrieved = service.retrieve({"query": "successful pattern", "account_id": "acc-b"})
    assert any(item.id == global_doc.id for item in retrieved["documents"])
    try:
        service.remember(title="orphan", content="no owner", scope_type="ACCOUNT")
        assert False, "unscoped account memory must fail closed"
    except IsolationError:
        pass
    try:
        service.retrieve({"query": "secret"})
        assert False, "production retrieve without account_id must fail closed"
    except AmbiguousAccount:
        pass


def test_platform_knowledge_does_not_cross_platforms():
    service = MemoryService.testing()
    service.remember(title="XHS platform", content="xiaohongshu only", scope_type="PLATFORM", platform="xiaohongshu")
    hits = service.search("xiaohongshu only", account_id="acc-b", platform="douyin")
    assert [item.title for item in hits if item.scope_type == "PLATFORM"] == []
    hits_xhs = service.search("xiaohongshu only", account_id="acc-b", platform="xiaohongshu")
    assert any(item.title == "XHS platform" for item in hits_xhs)


def test_retrieval_facade_requires_account_id():
    remember(MemoryFact("iso-1", "content", "owned hook", "worked", "analytics", account_id="acc-iso"))
    result = retrieve({"query": "hook", "account_id": "acc-iso"})
    assert result["account_id"] == "acc-iso"
    try:
        retrieve({"query": "hook"})
        assert False, "retrieve without account_id must fail closed"
    except IsolationError:
        pass
