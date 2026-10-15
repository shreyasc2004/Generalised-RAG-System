from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from filelock import FileLock

from .config import Settings
from .embeddings import Embedder, LocalEmbedder, split_text
from .loaders import SUPPORTED, load_document
from .models import Match, QueryRequest, QueryResponse, SyncReport


class RAGService:
    """Folder ingestion and retrieval; no generation model or API key required."""

    def __init__(self, settings: Settings | None = None, *, embedder: Embedder | None = None):
        self.settings = settings or Settings.from_env()
        cfg = self.settings
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = cfg.data_dir / f"{cfg.collection}.manifest.json"
        self.lock = FileLock(str(cfg.data_dir / f"{cfg.collection}.lock"), timeout=120)
        if not self.manifest_path.exists():
            cfg.kb_dir.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder or LocalEmbedder(cfg.data_dir / "models")
        with self.lock:
            self.client = chromadb.PersistentClient(
                path=str(cfg.data_dir / "chroma"), settings=ChromaSettings(anonymized_telemetry=False)
            )
            self.collection = self.client.get_or_create_collection(
                name=cfg.collection, embedding_function=None,
                configuration={"hnsw": {"space": "cosine"}},
                metadata={"rag_embedding": self.embedder.name, "rag_kb": str(cfg.kb_dir)},
            )
            metadata = self.collection.metadata or {}
            if metadata.get("rag_embedding") != self.embedder.name or metadata.get("rag_kb") != str(cfg.kb_dir):
                raise ValueError("Collection belongs to a different KB or embedding model; use another RAG_COLLECTION.")
            self._read_manifest()

    def _read_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {"version": 1, "kb": str(self.settings.kb_dir), "files": {}}
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if manifest.get("version") != 1 or manifest.get("kb") != str(self.settings.kb_dir):
            raise ValueError("Incompatible manifest; use another RAG_COLLECTION.")
        if not isinstance(manifest.get("files"), dict):
            raise ValueError("Invalid index manifest.")
        return manifest

    def _save_manifest(self, manifest: dict) -> None:
        # The caller holds the file lock. Queries see only committed revisions.
        temporary = self.manifest_path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.manifest_path)

    def _revision(self, source: str, data: bytes) -> str:
        cfg = self.settings
        signature = f"pipeline-v1:{self.embedder.name}:{cfg.chunk_tokens}:{cfg.overlap_tokens}:{source}:"
        return hashlib.sha256(signature.encode() + data).hexdigest()

    def warmup(self) -> None:
        with self.lock:
            self.embedder.embed(["Initialize local retrieval."])

    def sync(self) -> SyncReport:
        with self.lock:
            return self._sync()

    def _sync(self) -> SyncReport:
        cfg = self.settings
        if not cfg.kb_dir.is_dir():
            raise FileNotFoundError(f"Knowledge folder is unavailable: {cfg.kb_dir}; index was retained.")
        manifest = self._read_manifest()
        report = SyncReport()
        seen: set[str] = set()
        # Finish the scan before updating anything. Traversal failures abort pruning.
        paths: list[Path] = []

        def scan_error(error: OSError) -> None:
            raise error

        for directory, dirs, names in os.walk(cfg.kb_dir, followlinks=False, onerror=scan_error):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (Path(directory) / d).is_symlink())
            paths.extend(Path(directory) / name for name in sorted(names) if not name.startswith("."))
        for path in paths:
            source = path.relative_to(cfg.kb_dir).as_posix()
            # Even failed/unsupported files are seen, preserving previous good data.
            seen.add(source)
            if path.is_symlink() or not path.resolve().is_relative_to(cfg.kb_dir):
                report.skipped.append(source)
                continue
            if path.suffix.lower() not in SUPPORTED:
                report.skipped.append(source)
                continue
            try:
                if path.stat().st_size > cfg.max_file_bytes:
                    raise ValueError(f"File exceeds the {cfg.max_file_bytes}-byte limit.")
                with path.open("rb") as stream:
                    data = stream.read(cfg.max_file_bytes + 1)
                if len(data) > cfg.max_file_bytes:
                    raise ValueError("File exceeds the size limit.")
                revision = self._revision(source, data)
                previous = manifest["files"].get(source)
                if previous and previous["revision"] == revision:
                    report.unchanged += 1
                    continue
                sections = load_document(path, data)
                texts, metadatas, ids = [], [], []
                for section in sections:
                    for text in split_text(section.text, self.embedder, cfg.chunk_tokens, cfg.overlap_tokens):
                        index = len(texts)
                        metadata = {"source": source, "revision": revision, "chunk_index": index}
                        if section.page is not None:
                            metadata["page"] = section.page
                        texts.append(text)
                        metadatas.append(metadata)
                        ids.append(f"{revision}:{index}")
                if not texts:
                    raise ValueError("No indexable text tokens found.")
                batch_size = min(64, self.client.get_max_batch_size())
                for start in range(0, len(ids), batch_size):
                    end = start + batch_size
                    vectors = self.embedder.embed(texts[start:end])
                    self.collection.upsert(
                        ids=ids[start:end], documents=texts[start:end],
                        metadatas=metadatas[start:end], embeddings=vectors,
                    )
                # Publish only after every chunk was embedded and stored successfully.
                manifest["files"][source] = {"revision": revision, "chunks": len(ids)}
                try:
                    self._save_manifest(manifest)
                except Exception:
                    if previous is None:
                        manifest["files"].pop(source, None)
                    else:
                        manifest["files"][source] = previous
                    raise
                report.indexed += 1
            except Exception as exc:
                report.errors[source] = str(exc)

        missing = set(manifest["files"]) - seen
        if missing:
            for source in missing:
                del manifest["files"][source]
            self._save_manifest(manifest)
            report.deleted = len(missing)
        elif not self.manifest_path.exists():
            self._save_manifest(manifest)

        # Collect abandoned batches and old revisions. Failed cleanup never exposes them.
        active = {entry["revision"] for entry in manifest["files"].values()}
        try:
            offset, stale = 0, []
            while True:
                batch = self.collection.get(limit=1000, offset=offset, include=["metadatas"])
                if not batch["ids"]:
                    break
                stale.extend(id_ for id_, meta in zip(batch["ids"], batch["metadatas"]) if meta["revision"] not in active)
                offset += len(batch["ids"])
            batch_size = min(1000, self.client.get_max_batch_size())
            for start in range(0, len(stale), batch_size):
                self.collection.delete(ids=stale[start:start + batch_size])
        except Exception as exc:
            report.errors["__cleanup__"] = str(exc)
        report.chunks = sum(entry["chunks"] for entry in manifest["files"].values())
        return report

    def status(self) -> dict:
        with self.lock:
            manifest = self._read_manifest()
            return {
                "kb_dir": str(self.settings.kb_dir), "data_dir": str(self.settings.data_dir),
                "collection": self.settings.collection, "embedding_model": self.embedder.name,
                "documents": len(manifest["files"]),
                "chunks": sum(entry["chunks"] for entry in manifest["files"].values()),
            }

    def retrieve(self, query: str, *, top_k: int = 5, max_chars: int = 12000, source: str | None = None) -> QueryResponse:
        request = QueryRequest(query=query, top_k=top_k, max_chars=max_chars, source=source)
        with self.lock:
            files = self._read_manifest()["files"]
            revisions = [entry["revision"] for name, entry in files.items() if source is None or source == name]
            response = QueryResponse(query=request.query)
            if not revisions:
                return response
            count = sum(entry["chunks"] for name, entry in files.items() if source is None or source == name)
            raw = self.collection.query(
                query_embeddings=self.embedder.embed([request.query]),
                n_results=min(request.top_k, count),
                where={"revision": {"$in": revisions}}, include=["documents", "metadatas", "distances"],
            )
            parts = []
            for id_, text, meta, distance in zip(raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0]):
                label = f"[{len(parts) + 1}] {meta['source']}"
                if "page" in meta:
                    label += f" (page {meta['page']})"
                prefix = ("\n\n" if parts else "") + label + "\n"
                remaining = request.max_chars - sum(len(part) for part in parts) - len(prefix)
                if remaining <= 0:
                    break
                selected = text[:remaining]
                parts.append(prefix + selected)
                response.matches.append(Match(
                    id=id_, text=selected, source=meta["source"], page=meta.get("page"),
                    chunk_index=meta["chunk_index"], distance=distance, truncated=len(selected) < len(text),
                ))
            response.context = "".join(parts)
            return response

