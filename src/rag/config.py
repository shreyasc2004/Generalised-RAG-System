from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # Paths are anchored to this project, never the caller's working directory.
    root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    kb_dir: Path | None = None
    data_dir: Path | None = None
    collection: str = "knowledge_base"
    chunk_tokens: int = 220
    overlap_tokens: int = 32
    max_file_bytes: int = 50 * 1024 * 1024

    def __post_init__(self) -> None:
        root = Path(self.root).resolve()
        object.__setattr__(self, "root", root)
        for name, default in (("kb_dir", "Knowledge base/kb"), ("data_dir", ".rag")):
            value = Path(getattr(self, name) or default)
            object.__setattr__(self, name, (root / value).resolve())
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{1,61}[a-zA-Z0-9]", self.collection):
            raise ValueError("Collection must be 3–63 letters, digits, underscores or hyphens.")
        if not 0 <= self.overlap_tokens < self.chunk_tokens <= 254:
            raise ValueError("Require 0 <= overlap_tokens < chunk_tokens <= 254.")
        if self.max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive.")
        if self.data_dir == self.kb_dir or self.kb_dir in self.data_dir.parents:
            raise ValueError("The data directory must be outside the knowledge folder.")

    @classmethod
    def from_env(cls) -> Settings:
        kwargs = {}
        for env, key in (("RAG_ROOT", "root"), ("RAG_KB_DIR", "kb_dir"), ("RAG_DATA_DIR", "data_dir")):
            if os.environ.get(env):
                kwargs[key] = Path(os.environ[env])
        if os.environ.get("RAG_COLLECTION"):
            kwargs["collection"] = os.environ["RAG_COLLECTION"]
        for env, key in (("RAG_CHUNK_TOKENS", "chunk_tokens"), ("RAG_OVERLAP_TOKENS", "overlap_tokens")):
            if os.environ.get(env):
                kwargs[key] = int(os.environ[env])
        return cls(**kwargs)

