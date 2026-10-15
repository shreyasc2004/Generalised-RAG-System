"""Exercise actual local embeddings and persistent retrieval against sample inputs."""
from pathlib import Path

from rag import RAGService, Settings
from rag.connectors import LocalConnector


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    settings = Settings(root=root, kb_dir="examples/sample_kb", collection="smoke_knowledge")
    service = RAGService(settings)
    report = service.sync()
    assert not report.errors, report.errors
    result = LocalConnector(service).retrieve("What must new employees do before getting system access?", top_k=1)
    assert result.matches and result.matches[0].source == "onboarding.md", result
    assert "security training" in result.context
    reopened = RAGService(settings)
    assert reopened.retrieve("When does the cafeteria serve lunch?", top_k=1).matches[0].source == "cafeteria.md"
    print("PASS: actual local model, ingestion, semantic retrieval, source citations, and persisted collection")
    print(result.context)


if __name__ == "__main__":
    main()

