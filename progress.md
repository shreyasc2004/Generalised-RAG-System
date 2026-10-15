# Generalised RAG system progress

Last updated: 2026-10-15.

## Current status

The core retrieval scope from the requirements shared for Shreyas is implemented and working: documents in `Knowledge base/kb` are indexed into local ChromaDB, and Python/HTTP connectors provide retrieved evidence to a consuming application.

External context-builder integration and a clean installation on another machine remain unverified. The improvements below are proposed future work.

GitHub repository: [shreyasc2004/Generalised-RAG-System](https://github.com/shreyasc2004/Generalised-RAG-System).
The project has its own local Git repository on `main`. Git excludes knowledge documents (except the empty-folder placeholder), `.rag`, `.venv`, editor settings, Python caches, and environment files.

## Completed work

| Requirement | Implementation |
| --- | --- |
| Folder-based input | Reads supported documents recursively from `Knowledge base/kb`. |
| Document extraction | Supports UTF-8 text, Markdown, JSON, CSV, HTML, text PDFs, and DOCX. |
| Chunking and embeddings | Splits extracted text into overlapping token chunks and embeds locally with ONNX all-MiniLM-L6-v2 on CPU. |
| Local vector database | Creates and manages persistent embedded ChromaDB in `.rag/chroma`; no separate database server is required. |
| Setup scripts | `scripts/setup.py` and `setup.ps1` prepare the virtual environment, install dependencies, initialize storage, and download the embedding model. Python and initial internet access are prerequisites. |
| Incremental indexing | Skips unchanged files, indexes edits, and removes deleted documents during sync. Failed updates retain the previous successful version. |
| Automatic synchronization | Server startup indexes the folder; serving polls for changes every five seconds by default. |
| Query output | Returns context with citation labels and structured matches containing source, page when available, chunk index, cosine distance, and text. |
| Connectors | Provides `LocalConnector` for Python and `HTTPConnector` for applications using HTTP. |
| HTTP interface | Implements `/health`, `/status`, `/sync`, and `/query`. |
| Basic validation | Checks supported extensions, file size, readable/nonempty input, and query parameters; excludes hidden files and symlinks and reports per-file failures. |
| Documentation | README covers setup, operation, connectors, supported formats, limitations, and ideas for deeper validation. |

The implemented flow is:

```text
Knowledge base/kb -> extract -> chunk -> local embeddings -> persistent ChromaDB
Consumer query -> Python/HTTP connector -> retrieve -> context and source matches
```

## Verification completed

### Automated tests

Command run during this conversation:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Result: **20 passed in 3.14 seconds**. Tests use real persistent ChromaDB with deterministic test embeddings. Coverage includes persistence, incremental updates/deletions, failed updates, unpublished revisions, context budgets, loaders, and API/connector compatibility.

### Actual embedding retrieval

The existing knowledge index was queried using the actual local embedding model:

- Index status at verification: **1 document, 8,294 chunks**.
- Indexed source: `Dialogue_2015.txt`.
- `Tell me about dragons`: returned five passages about Skyrim's dragons, the Dragon War, and Dragonsreach.
- `Why were dragons worshipped as gods in Skyrim?`: retrieved relevant passages about dragon worship and the Dragon Cult.
- Full output: [.rag/dragon_query_results.json](.rag/dragon_query_results.json).

These queries demonstrate working retrieval on the current document; they do not establish retrieval quality across every supported document type or topic.

## Findings and current limits

- Retrieved dialogue contains internal game IDs, quest codes, and neighboring lines that are not useful to the question.
- Token-based chunk boundaries sometimes split sentences or structured dialogue records midway.
- Retrieval returns the nearest passages even when the documents do not contain a good answer; no answerability check or reranking is implemented.
- Image-only/scanned PDFs need OCR, which is not included.
- A consuming context builder has not been supplied, so its actual integration is pending.
- Fresh setup on another machine has not been verified in this session.

## Next steps

The original core scope is complete. Suggested follow-up work, in order:

1. **Verify actual context-builder integration.** Obtain its expected input/output contract, connect through the Python or HTTP interface, and confirm it receives useful context and citations.
2. **Improve passage quality.** Preserve sentence/paragraph boundaries within embedding limits. Consider optional structured-export parsing for dialogue files, keeping document identifiers as metadata where useful and preserving provenance.
3. **Measure retrieval quality.** Build a small evaluation set with questions and expected source passages, including broad questions, paraphrases, and questions unsupported by the documents. Use results to decide whether reranking or an answerability check is needed.
4. **Verify fresh setup.** Run the setup and a retrieval smoke test in a clean environment, documenting prerequisites and any installation issues.
5. **Add deeper input validation later.** Validate file signatures, encoding, parser/resource limits, and extracted text quality before indexing; produce clear per-file reports. Add OCR or quarantine workflows only if required.

A context builder assembles retrieved evidence, the user's question, and instructions for a language model. Conversational answer generation is outside the original retrieval scope and is only needed if the consuming application requires it.

## Main project files

- `src/rag/service.py`: ingestion, synchronization, persistence, retrieval.
- `src/rag/embeddings.py`: local embeddings and chunking.
- `src/rag/loaders.py`: document extraction.
- `src/rag/connectors.py`: Python and HTTP connectors.
- `src/rag/api.py`: HTTP endpoints.
- `scripts/setup.py`, `setup.ps1`: setup entry points.
- `README.md`: operating and integration instructions.
- `PROJECT_CONTEXT.md`: conversation handoff and scope decisions.

## Useful commands

Run from `C:\Users\shre9\Desktop\RAG`:

```powershell
# Initial setup
python scripts/setup.py

# Start the server and folder watcher
.\.venv\Scripts\python.exe -m rag serve

# Inspect the index
.\.venv\Scripts\python.exe -m rag status

# Explicitly synchronize documents
.\.venv\Scripts\python.exe -m rag sync

# Retrieve evidence
.\.venv\Scripts\python.exe -m rag query "Tell me about dragons"

# Run tests (requires development dependencies)
.\.venv\Scripts\python.exe -m pytest -q
```

Default server address: `http://127.0.0.1:8000`. Interactive API docs: `http://127.0.0.1:8000/docs`.

## Continuing in a future session

Ask the assistant: "Read progress.md, PROJECT_CONTEXT.md, and README.md to catch up on this RAG project."

Choose a next task before starting implementation; the follow-up improvements above have not yet been implemented.
