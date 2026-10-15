"""Public connector for in-process context builders."""

from .config import Settings
from .service import RAGService

__all__ = ["RAGService", "Settings"]

