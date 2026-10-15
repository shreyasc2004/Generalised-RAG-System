from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException
from filelock import Timeout

from .models import QueryRequest, QueryResponse, SyncReport
from .service import RAGService

logger = logging.getLogger(__name__)


def create_app(service: RAGService | None = None, *, watch_interval: float = 0) -> FastAPI:
    if watch_interval < 0:
        raise ValueError("watch_interval cannot be negative.")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.rag = service or RAGService()
        report = await asyncio.to_thread(app.state.rag.sync)
        app.state.last_sync = report
        if report.errors:
            logger.warning("Startup indexing errors: %s", report.errors)

        async def watch():
            while True:
                await asyncio.sleep(watch_interval)
                try:
                    result = await asyncio.to_thread(app.state.rag.sync)
                    app.state.last_sync = result
                    if result.errors:
                        logger.warning("Indexing errors: %s", result.errors)
                except Exception:
                    logger.exception("Folder sync failed; retaining the last committed index")

        task = asyncio.create_task(watch()) if watch_interval else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Local Folder RAG", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/status")
    def status():
        return {**app.state.rag.status(), "last_sync": app.state.last_sync.model_dump()}

    @app.post("/sync", response_model=SyncReport)
    def sync():
        try:
            report = app.state.rag.sync()
            app.state.last_sync = report
            return report
        except (OSError, ValueError, Timeout) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/query", response_model=QueryResponse)
    def query(request: QueryRequest):
        try:
            return app.state.rag.retrieve(**request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (OSError, Timeout) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return app

