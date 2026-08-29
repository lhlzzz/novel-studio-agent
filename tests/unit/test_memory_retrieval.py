from memory.models import MemoryFact
from memory.retrieval import remember, retrieve
from memory.writeback import write_patterns


def test_retrieve_before_generate_returns_namespaces():
    remember(MemoryFact("1", "content", "hook A", "worked on x", "analytics"))
    result = retrieve({"query": "hook"})
    assert result["historical_content"]
    written = write_patterns({"successful_pattern": "hook A", "confidence": 0.9})
    assert written["written"] >= 1
