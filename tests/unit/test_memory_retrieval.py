from memory.models import MemoryFact
from memory.retrieval import remember, retrieve
from memory.writeback import write_patterns


def test_retrieve_before_generate_returns_namespaces():
    remember(MemoryFact("1", "content", "hook A", "worked on x", "analytics", account_id="acc-test"))
    result = retrieve({"query": "hook", "account_id": "acc-test"})
    assert result["historical_content"]
    written = write_patterns({"successful_pattern": "hook A", "confidence": 0.9, "account_id": "acc-test"})
    assert written["written"] >= 1
