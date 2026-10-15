"""Run after indexing documents, from any directory using the project interpreter."""
from rag.connectors import LocalConnector

connector = LocalConnector()
result = connector.retrieve("What does our documentation say about onboarding?", top_k=4)
print(result.context)
for match in result.matches:
    print(f"Source: {match.source}, page: {match.page}, distance: {match.distance:.3f}")

