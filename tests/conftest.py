import hashlib
import math
import re

import pytest

from rag import RAGService, Settings


class TestEmbedder:
    """Network-free deterministic vectors; integration tests still use real Chroma."""
    __test__ = False
    name = "test-bag-of-words-v1"

    def __init__(self):
        self.fail = False
        self.calls = 0

    def offsets(self, text):
        return [match.span() for match in re.finditer(r"\S+", text)]

    def embed(self, texts):
        self.calls += 1
        if self.fail:
            raise RuntimeError("Simulated embedding failure")
        result = []
        for text in texts:
            vector = [0.0] * 128
            for word in re.findall(r"\w+", text.lower()):
                index = int(hashlib.sha256(word.encode()).hexdigest(), 16) % len(vector)
                vector[index] += 1
            norm = math.sqrt(sum(value * value for value in vector)) or 1
            result.append([value / norm for value in vector])
        return result


@pytest.fixture
def service(tmp_path):
    return RAGService(Settings(root=tmp_path, chunk_tokens=20, overlap_tokens=4), embedder=TestEmbedder())

