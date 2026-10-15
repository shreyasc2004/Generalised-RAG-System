from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    top_k: int = Field(default=5, ge=1, le=100)
    max_chars: int = Field(default=12000, ge=1, le=100000)
    source: str | None = Field(default=None, min_length=1)

    @field_validator("query")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query cannot be blank.")
        return value.strip()


class Match(BaseModel):
    id: str
    text: str
    source: str
    page: int | None = None
    chunk_index: int
    distance: float
    truncated: bool = False


class QueryResponse(BaseModel):
    query: str
    context: str = ""
    matches: list[Match] = Field(default_factory=list)


class SyncReport(BaseModel):
    indexed: int = 0
    unchanged: int = 0
    deleted: int = 0
    skipped: list[str] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)
    chunks: int = 0

