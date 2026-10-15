# RAG project handoff

Last updated: 2026-10-15.

## Agreed scope and status

The user's requirements (the message referred to as being for Shreyas) are:
- Read supported knowledge documents from `Knowledge base/kb`, including subfolders.
- Extract text, chunk it, embed locally, and store it in persistent local ChromaDB.
- Supply setup scripts so users do not install or operate a separate Chroma server.
- Provide query connectors for a separate context builder.
- Defer deeper input/structure validation, while documenting how it could work.

The core retrieval scope is implemented and working. This is a functional first version, not a claim of exhaustive production validation. Python and HTTP connectors exist; integration with an actual external context builder has not been performed because none was provided. A fresh installation on another machine was not verified in this conversation.

The user asked whether the assigned scope was done and was told yes, with external context-builder integration separate. Do not treat conversational answer generation as a missing requirement. The service returns retrieved evidence; prompt construction and answer generation belong to a consuming application. The user asked what a context builder means: it assembles the question, retrieved passages, instructions, and optionally conversation history for a language model.

## Implementation

- `src/rag/service.py`: indexing, persistent Chroma, incremental sync, retrieval, citation context.
- `src/rag/embeddings.py`: local ONNX all-MiniLM-L6-v2 embeddings and overlapping token chunks.
- `src/rag/loaders.py`: supported document extraction.
- `src/rag/connectors.py`: LocalConnector and HTTPConnector with a shared retrieval contract.
- `src/rag/api.py`: health, status, sync, and query endpoints.
- `scripts/setup.py` and `setup.ps1`: dependency installation, local initialization, and model download.
- `README.md`: setup, supported formats, API, integration, limitations, and deferred validation ideas.
- `.rag/`: persistent vectors, manifest, model cache, and saved query output.

## Verified during this conversation

- `.\.venv\Scripts\python.exe -m pytest -q`: 20 passed in 3.14 seconds. These tests use deterministic test embeddings with real Chroma.
- Actual local embedding retrieval was also exercised against the existing knowledge index.
- Status at verification: 1 indexed document, 8,294 chunks; source `Dialogue_2015.txt`.
- Query `Tell me about dragons`: five top matches from the Skyrim dialogue file, discussing dragons returning, the Dragon War, and Dragonsreach.
- Query `Why were dragons worshipped as gods in Skyrim?`: retrieved relevant worship/Dragon Cult passages.
- Complete query results and status are saved in `.rag/dragon_query_results.json`.

The output includes internal game metadata (FormID and quest codes), unrelated neighboring dialogue, and chunks that start/end mid-sentence. Retrieval works, but passage quality could improve. No code changes were made for these findings.

## Optional future work

No further implementation has been authorized in this conversation. Possible next steps if requested:
1. Integrate and verify the user's actual context builder.
2. Improve general sentence/paragraph chunk boundaries; optionally add structured dialogue parsing without imposing a Skyrim-specific format on all documents.
3. Evaluate retrieval with questions and expected passages, including unanswerable questions. Current retrieval returns nearest passages even without a good answer.
4. Add deeper validation before extraction: file signatures, parser/resource limits, text quality, and clear per-file reports. Basic checks already exist.

## Useful PowerShell commands

Run from `C:\Users\shre9\Desktop\RAG`:

```powershell
.\.venv\Scripts\python.exe -m rag status
.\.venv\Scripts\python.exe -m rag query "Tell me about dragons"
.\.venv\Scripts\python.exe -m rag serve
.\.venv\Scripts\python.exe -m pytest -q
```

Serving indexes at startup and polls for document changes. Default HTTP address: `http://127.0.0.1:8000`.

## Resume context

Read this file and README.md before continuing. Preserve the scope distinction above, inspect current files/state as needed, and wait for the user's next requested task rather than automatically beginning optional improvements.
