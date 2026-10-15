"""Stable contracts for context builders, in-process or over HTTP."""
from __future__ import annotations

from typing import Protocol

import httpx

from .models import QueryRequest, QueryResponse
from .service import RAGService


class ContextConnector(Protocol):
    def retrieve(self, query: str, *, top_k: int = 5, max_chars: int = 12000, source: str | None = None) -> QueryResponse: ...


class LocalConnector:
    def __init__(self, service: RAGService | None = None):
        self.service = service or RAGService()

    def retrieve(self, query: str, *, top_k: int = 5, max_chars: int = 12000, source: str | None = None) -> QueryResponse:
        return self.service.retrieve(query, top_k=top_k, max_chars=max_chars, source=source)


class HTTPConnector:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def retrieve(self, query: str, *, top_k: int = 5, max_chars: int = 12000, source: str | None = None) -> QueryResponse:
        request = QueryRequest(query=query, top_k=top_k, max_chars=max_chars, source=source)
        response = httpx.post(f"{self.base_url}/query", json=request.model_dump(), timeout=self.timeout)
        response.raise_for_status()
        return QueryResponse.model_validate(response.json())

