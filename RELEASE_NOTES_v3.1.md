# AGENT ALINE X — Release Notes v3.1

**Status:** Release Candidate (P7 Final QA)
**Updated:** 2026-07-01

This release covers phases P0 through P7 of the v3.1 backend/agent-intelligence
rebuild. Each phase was implemented, tested, and runtime-verified before the next
began.

---

## P0 — Path Safety & Model Router
Foundational safety layer: `is_allowed_path()` enforces workspace-root containment
(blocks traversal, sibling-prefix folders, and any path outside allowed roots).
`select_model_for_prompt()` introduced keyword-based routing to normal-chat, code/debug,
and audit/QA models.

## P1 — Dynamic Model Discovery & Workspace Config
Replaced the static model list with live Ollama tag discovery (`discover_models_cached`,
30s cache) plus automatic fallback if a selected model is unavailable
(`resolve_chat_model`). Added a configurable active/allowed workspace system
(`agent_config.json`, `GET/POST /api/workspace`) with strict `is_safe_workspace_path`
validation (blocks drive roots, `C:\Windows`, `C:\Users`, empty paths).

## P2 — Performance Metadata
Every `/api/chat` response now carries a `metadata` block (`build_metadata`) with
request id, selected/resolved model, route reason, duration, fallback info, and
prompt/context sizes. Exposed via `GET /api/performance` with a capped 20-record
in-memory history.

## P3 — Context Trimming & Quality Controls
`trim_context_chunks()` enforces a hard character budget per response mode
(Quick/Balanced/Detailed) while always preserving the most recent chunk. Added
per-route "quality profiles" (`normal_chat`, `code_debug`, `audit_qa`, `fallback`)
with a universal hallucination-safety addendum injected into every model call.

## P4 — File Context Intelligence
Added safe, explicit file-context packing: the frontend can send `selected_files`,
which are resolved through `safe_resolve_relative` (blocks traversal, secret filenames,
oversized files) and packed into `[Project File Context]` chunks for the model.

## P5 — Embedding Memory (Project Memory Search)
Introduced `project_memory.py`: a local project indexer/search engine
(`reindex_project_memory`, `search_memory_index`) using Ollama embeddings when
available, with automatic fallback to keyword search when Ollama/embedding model is
offline. Secret and noise files (`.git`, `node_modules`, credentials, etc.) are never
indexed.

## P5.1 — Runtime Memory Activation
Wired natural-language prompts ("search project memory for X", "explain files
involved", etc.) to automatically trigger memory retrieval in `/api/chat`, including
safe auto-reindex when the index is missing/empty, without ever silently failing —
empty results return clear metadata instead of a crash or hallucinated answer.

## P5.2 — Ranking Polish
Added a `production_first` ranking profile: production source files are boosted,
matching test files are downranked by default (but not when the query is explicitly
about tests), with per-result ranking notes surfaced in the API response for
transparency.

## P6 — Command Execution Planner
Added a pure-classification command planner (`plan_command`) with three risk tiers —
**safe** (read-only, auto-runs), **caution** (requires explicit `confirmed: true`),
**blocked** (destructive patterns, e.g. `Remove-Item -Recurse -Force`, `git reset --hard`,
`docker system prune` — never executed regardless of confirmation). Exposed via
`POST /api/commands/plan` (classify only) and `POST /api/commands/run-free`
(plan-first execution for free-form commands). Also added `summarize_output()` for
compact pass/fail/error summaries and `GET /api/commands/templates` for common safe
workflows. The original `POST /api/commands/run` (fixed `command_id` allowlist) is
preserved unchanged for backward compatibility with the existing frontend.

## P6.1 — Test Collection Hygiene
Added `pytest.ini` with `norecursedirs` excluding all `backup*` folders, fixing a
pytest module-import collision caused by stale `test_safety.py` copies inside backup
directories. `py -3.11 -m pytest -q` now runs cleanly from the project root with no
`--ignore` flags required.

## P7 — Final QA Dashboard & Release Packaging
Added `release_info.json` (name/version/stage/status/completed phases/ports) and a
new read-only `GET /api/release/status` endpoint summarizing: version, release stage,
completed phases, active workspace, cached model-discovery status, a lightweight
memory-index summary (file/chunk counts, no reindex triggered), command-planner
enabled flag, and recommended test/build commands. Documentation refreshed
(`RUN_COMMANDS.md` rewritten for the current FastAPI+Vite stack, replacing the
outdated Docker/Open WebUI instructions; this file; `FINAL_QA_CHECKLIST.md` added).
No UI redesign — frontend untouched.

---

## Verified test counts

| Milestone | pytest result |
|---|---|
| P6 complete | 65 passed |
| P6.1 (hygiene fix) | 65 passed, no `--ignore` flags needed |
| P7 (this release) | 68 passed (65 + 3 new P7 tests) |

---

*Project: AGENT ALINE X | v3.1 Release Candidate | P7 Final QA*
