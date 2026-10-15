from __future__ import annotations

import argparse
import json
import sys

from .service import RAGService


def main() -> int:
    parser = argparse.ArgumentParser(description="Local knowledge-folder RAG")
    commands = parser.add_subparsers(dest="command", required=True)
    initialize = commands.add_parser("init", help="Create the managed database and knowledge folder")
    initialize.add_argument("--download-model", action="store_true")
    commands.add_parser("sync", help="Index new/changed files and remove missing files")
    commands.add_parser("status")
    query = commands.add_parser("query")
    query.add_argument("text")
    query.add_argument("--top-k", type=int, default=5)
    query.add_argument("--max-chars", type=int, default=12000)
    query.add_argument("--source")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--watch-interval", type=float, default=5)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            import uvicorn
            from .api import create_app

            uvicorn.run(create_app(watch_interval=args.watch_interval), host=args.host, port=args.port)
            return 0
        service = RAGService()
        if args.command == "init":
            if args.download_model:
                service.warmup()
            result = service.status()
        elif args.command == "sync":
            report = service.sync()
            print(report.model_dump_json(indent=2))
            return 1 if report.errors else 0
        elif args.command == "status":
            result = service.status()
        else:
            result = service.retrieve(args.text, top_k=args.top_k, max_chars=args.max_chars, source=args.source).model_dump()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"RAG error: {exc}", file=sys.stderr)
        return 1

