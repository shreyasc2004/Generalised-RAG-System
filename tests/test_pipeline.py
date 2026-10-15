import shutil

import pytest
from fastapi.testclient import TestClient

from rag import RAGService, Settings
from rag.api import create_app
from rag.connectors import HTTPConnector, LocalConnector
from rag.embeddings import split_text
from conftest import TestEmbedder


def put(service, name, text):
    path = service.settings.kb_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_sync_retrieval_and_persistence(service):
    put(service, "policies/onboarding.md", "Onboarding employees receive a laptop and security training.")
    put(service, "lunch.txt", "Lunch includes pasta soup salad and sandwiches.")
    report = service.sync()
    assert report.indexed == 2 and report.chunks == 2 and not report.errors
    calls = service.embedder.calls
    assert service.sync().unchanged == 2
    assert service.embedder.calls == calls
    result = LocalConnector(service).retrieve("onboarding employees laptop", top_k=1)
    assert result.matches[0].source == "policies/onboarding.md"
    assert "[1] policies/onboarding.md" in result.context
    reopened = RAGService(service.settings, embedder=TestEmbedder())
    assert reopened.status()["documents"] == 2
    assert reopened.retrieve("onboarding").matches


def test_edits_remove_obsolete_chunks_and_deletes_prune(service):
    path = put(service, "policy.txt", " ".join(["old"] * 90))
    assert service.sync().chunks > 1
    path.write_text("New replacement policy.", encoding="utf-8")
    report = service.sync()
    assert report.indexed == 1 and report.chunks == 1
    assert service.collection.count() == 1
    assert service.retrieve("policy").matches[0].text == "New replacement policy."
    path.unlink()
    assert service.sync().deleted == 1
    assert service.collection.count() == 0
    assert service.retrieve("policy").matches == []


def test_invalid_document_keeps_previous_good_version_and_indexes_others(service):
    path = put(service, "policy.json", '{"policy": "Security training is mandatory"}')
    service.sync()
    path.write_text("{invalid", encoding="utf-8")
    put(service, "good.txt", "A second valid document.")
    report = service.sync()
    assert "policy.json" in report.errors
    assert report.indexed == 1 and service.status()["documents"] == 2
    assert "mandatory" in service.retrieve("security", source="policy.json").context


def test_failed_embedding_does_not_publish_replacement(service):
    path = put(service, "policy.txt", "The original policy is retained.")
    service.sync()
    path.write_text("A failed replacement.", encoding="utf-8")
    service.embedder.fail = True
    assert "policy.txt" in service.sync().errors
    service.embedder.fail = False
    assert "original" in service.retrieve("policy").context
    assert service.sync().indexed == 1
    assert "replacement" in service.retrieve("policy").context


def test_uncommitted_revision_is_never_returned_and_is_collected(service):
    put(service, "good.txt", "Active document content.")
    service.sync()
    service.collection.upsert(
        ids=["orphan:0"], documents=["Uncommitted secret content"],
        embeddings=service.embedder.embed(["Uncommitted secret content"]),
        metadatas=[{"revision": "orphan", "source": "good.txt", "chunk_index": 0}],
    )
    assert all(match.id != "orphan:0" for match in service.retrieve("secret", top_k=100).matches)
    service.sync()
    assert service.collection.count() == 1


def test_partial_batches_do_not_publish_and_retry_recovers(service, monkeypatch):
    path = put(service, "long.txt", "Original content remains searchable.")
    service.sync()
    path.write_text(" ".join(f"word{i}" for i in range(1500)), encoding="utf-8")
    original = service.embedder.embed
    calls = 0

    def fail_second_batch(texts):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Second batch failed")
        return original(texts)

    monkeypatch.setattr(service.embedder, "embed", fail_second_batch)
    assert "long.txt" in service.sync().errors
    monkeypatch.setattr(service.embedder, "embed", original)
    assert "Original content" in service.retrieve("original").context
    assert service.collection.count() == 1
    assert service.sync().indexed == 1
    assert "Original content" not in service.retrieve("word0").context


def test_context_budget_source_filter_and_empty_index(service):
    assert service.retrieve("nothing").matches == []
    put(service, "a.txt", "A document about laptops and onboarding procedures.")
    put(service, "b.txt", "A document about cooking meals.")
    service.sync()
    result = service.retrieve("laptops", source="a.txt", max_chars=22)
    assert len(result.context) <= 22
    assert len(result.matches) == 1 and result.matches[0].truncated
    assert result.matches[0].source == "a.txt"
    assert service.retrieve("laptops", source="missing.txt").matches == []
    assert service.retrieve("laptops", max_chars=1).context == ""


def test_missing_kb_preserves_index(service):
    put(service, "a.txt", "An existing document.")
    service.sync()
    shutil.rmtree(service.settings.kb_dir)
    with pytest.raises(FileNotFoundError):
        service.sync()
    assert service.status()["documents"] == 1
    reopened = RAGService(service.settings, embedder=TestEmbedder())
    assert not reopened.settings.kb_dir.exists()
    assert reopened.retrieve("existing").matches


def test_settings_guardrails_and_reindex_chunk_change(service):
    with pytest.raises(ValueError):
        Settings(root=service.settings.root, data_dir="Knowledge base/kb/data")
    with pytest.raises(ValueError):
        Settings(chunk_tokens=20, overlap_tokens=20)
    put(service, "a.txt", " ".join(["content"] * 60))
    service.sync()
    new = RAGService(Settings(root=service.settings.root, chunk_tokens=40, overlap_tokens=5), embedder=TestEmbedder())
    assert new.sync().indexed == 1
    assert new.collection.count() == 2
    with pytest.raises(ValueError, match="different KB"):
        RAGService(Settings(root=service.settings.root, kb_dir="another-kb"), embedder=TestEmbedder())


def test_unsupported_hidden_and_oversized_files_are_reported(service):
    put(service, "image.png", "Not a supported document")
    put(service, ".hidden.txt", "Hidden data")
    put(service, "visible.txt", "Short content")
    small = RAGService(Settings(root=service.settings.root, max_file_bytes=5), embedder=TestEmbedder())
    report = small.sync()
    assert report.skipped == ["image.png"]
    assert "visible.txt" in report.errors
    assert ".hidden.txt" not in report.errors
    assert report.chunks == 0


def test_api_and_both_connectors(service, monkeypatch):
    put(service, "onboarding.md", "Employees must complete onboarding training.")
    with TestClient(create_app(service)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/status").json()["documents"] == 1
        assert client.post("/query", json={"query": "  "}).status_code == 422
        assert client.post("/query", json={"query": "training", "top_k": 0}).status_code == 422
        assert client.post("/query", json={"query": "training", "max_chars": 0}).status_code == 422
        monkeypatch.setattr("rag.connectors.httpx.post", lambda url, **kw: client.post("/query", json=kw["json"]))
        remote = HTTPConnector().retrieve("training")
        local = LocalConnector(service).retrieve("training")
        assert remote.model_dump() == local.model_dump()
        assert client.post("/sync").json()["unchanged"] == 1


def test_token_overlap_preserves_text():
    text = "zero one two three four five six seven eight nine"
    chunks = split_text(text, TestEmbedder(), 4, 1)
    assert chunks == ["zero one two three", "three four five six", "six seven eight nine"]

