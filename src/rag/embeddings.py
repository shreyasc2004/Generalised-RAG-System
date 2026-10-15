from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Protocol


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list: ...

    def offsets(self, text: str) -> list[tuple[int, int]]: ...


class LocalEmbedder:
    name = "all-MiniLM-L6-v2-onnx-v1"

    def __init__(self, cache_dir: Path) -> None:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        self.function = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
        # Keep model downloads inside this project rather than the user's home.
        self.function.DOWNLOAD_PATH = cache_dir / "all-MiniLM-L6-v2"

    @cached_property
    def tokenizer(self):
        from tokenizers import Tokenizer

        self.function(["Initialize the local embedding model."])
        tokenizer = Tokenizer.from_str(self.function.tokenizer.to_str())
        tokenizer.no_padding()
        tokenizer.no_truncation()
        return tokenizer

    def offsets(self, text: str) -> list[tuple[int, int]]:
        return self.tokenizer.encode(text, add_special_tokens=False).offsets

    def embed(self, texts: list[str]) -> list:
        for text in texts:
            if len(self.offsets(text)) > 254:
                raise ValueError("Embedding input exceeds 254 tokens; shorten the query.")
        return self.function(texts)


def split_text(text: str, embedder: Embedder, size: int, overlap: int) -> list[str]:
    """Use model token offsets to preserve source text without silent truncation."""
    offsets = embedder.offsets(text)
    chunks = []
    start = 0
    while start < len(offsets):
        end = min(start + size, len(offsets))
        chunk = text[offsets[start][0]:offsets[end - 1][1]].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(offsets):
            break
        start = end - overlap
    return chunks

