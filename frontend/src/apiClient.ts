// apiClient.ts — AGENT ALINE X Web bridge client.
// Talks to the local FastAPI backend_bridge.py (default http://127.0.0.1:8100).
// Every function fails soft (never throws to the caller) so the UI can
// fall back to Mock Mode when the backend is offline.

const metaEnv = (import.meta as unknown as { env?: Record<string, string> }).env || {};
const BACKEND_PORT = metaEnv.VITE_BACKEND_PORT || metaEnv.BACKEND_PORT || "8100";
const BASE_URL = metaEnv.VITE_BACKEND_URL || `http://127.0.0.1:${BACKEND_PORT}`;
const FETCH_TIMEOUT_MS = 240000;

async function safeFetch(path: string, init?: RequestInit): Promise<{ ok: boolean; data: any; error: string | null }> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE_URL}${path}`, { ...init, signal: controller.signal });
    window.clearTimeout(timer);
    if (!res.ok) {
      return { ok: false, data: null, error: `HTTP ${res.status}` };
    }
    const data = await res.json();
    return { ok: true, data, error: null };
  } catch (err) {
    window.clearTimeout(timer);
    const message = err instanceof Error ? err.message : "Unknown network error";
    return { ok: false, data: null, error: message };
  }
}

export type BridgeHealth = {
  backend: string;
  ollama: string;
  active_model: string;
  patch_mode: string;
  duration_ms?: number;
};

export type BridgeModels = {
  models: string[];
  default_model: string;
  ollama_reachable: boolean;
  status_detail: string;
  duration_ms?: number;
};

export type BridgeChatResponse = {
  response: string;
  model: string;
  duration_ms: number;
  response_length?: string;
  answer_source?: "fast_local" | "model";
  timeout_seconds?: number;
  context_chars?: number;
  context_chunks?: number;
  dropped_context_chunks?: number;
  bypassed_ollama?: boolean;
  suggestions?: string[];
  error?: boolean;
  selected_model?: string;
  route_reason?: string;
  fallback_used?: boolean;
  metadata?: {
    request_id?: string;
    selected_model?: string;
    resolved_model?: string;
    route_reason?: string;
    duration_ms?: number;
    fallback_used?: boolean;
    fallback_from?: string | null;
    fallback_to?: string | null;
    error?: string | null;
    prompt_length_chars?: number;
    context_length_chars?: number;
    created_at?: string;
    // P3
    context_trimmed?: boolean;
    original_context_length_chars?: number;
    final_context_length_chars?: number;
    response_mode?: string;
    quality_profile?: string;
    // P4
    file_context_used?: boolean;
    file_context_file_count?: number;
    file_context_chars?: number;
    file_context_trimmed?: boolean;
    // P5
    memory_context_used?: boolean;
    memory_context_chunks?: number;
    retrieval_mode?: string;
    memory_context_chars?: number;
    memory_index_missing?: boolean;
    memory_auto_reindexed?: boolean;
    memory_search_query?: string;
    memory_results_found?: number;
    ranking_profile?: string;
    production_boost_applied?: boolean;
    test_downrank_applied?: boolean;
    query_boost_applied?: boolean;
  };
};

export type BridgeModelTestResponse = {
  ok: boolean;
  model: string;
  message: string;
  duration_ms: number;
  status?: string;
  error?: boolean;
  // v3.1A — new benchmark fields from backend
  response?: string;
  timeout_used?: number;
  recommendation?: string;
};

export type FailureAnalysisBridge = {
  root_cause: string;
  likely_file: string;
  safe_fix_direction: string;
  next_test_command: string;
};

export type BridgeCommandResult = {
  command_id: string;
  label: string;
  ok: boolean;
  exit_code: number;
  output: string;
  duration_ms: number;
  failure_analysis?: FailureAnalysisBridge | null;
};

export type BridgeAuditResult = {
  steps: BridgeCommandResult[];
  pass: boolean;
  duration_ms: number;
  health_rating: "Healthy" | "Needs Attention" | "Critical";
};

export async function fetchHealth(): Promise<BridgeHealth | null> {
  const { ok, data } = await safeFetch("/api/health");
  return ok ? (data as BridgeHealth) : null;
}

export async function fetchModels(): Promise<BridgeModels | null> {
  const { ok, data } = await safeFetch("/api/models");
  return ok ? (data as BridgeModels) : null;
}

export async function testModelBridge(model: string, temperature: number): Promise<BridgeModelTestResponse | null> {
  const { ok, data } = await safeFetch("/api/models/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, temperature }),
  });
  return ok ? (data as BridgeModelTestResponse) : null;
}

export async function postChat(params: {
  message: string;
  model: string;
  context: string[];
  response_length: string;
  temperature: number;
  selected_files?: string[];
}): Promise<BridgeChatResponse | null> {
  const { ok, data } = await safeFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return ok ? (data as BridgeChatResponse) : null;
}

export type ProjectSearchResult = {
  relative_path: string;
  file_name: string;
  extension: string;
  snippet: string;
  score: number;
  size_bytes: number;
  safe_to_read: boolean;
};

export type ProjectSearchResponse = {
  query: string;
  active_workspace: string;
  results: ProjectSearchResult[];
  error?: string;
};

export async function searchProject(query: string): Promise<ProjectSearchResponse | null> {
  const { ok, data } = await safeFetch(`/api/project/search?q=${encodeURIComponent(query)}`);
  return ok ? (data as ProjectSearchResponse) : null;
}


export async function runCommandBridge(commandId: string): Promise<BridgeCommandResult | null> {
  const { ok, data } = await safeFetch("/api/commands/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command_id: commandId }),
  });
  return ok ? (data as BridgeCommandResult) : null;
}

export async function runFullAuditBridge(): Promise<BridgeAuditResult | null> {
  const { ok, data } = await safeFetch("/api/audit/full", { method: "POST" });
  return ok ? (data as BridgeAuditResult) : null;
}

export type FileEntry = {
  name: string;
  type: "DIR" | "FILE";
  size: number | null;
  locked: boolean;
};

export type FileListResult = {
  entries: FileEntry[];
  error: string | null;
  path?: string;
  duration_ms?: number;
};

export type FileLine = {
  line: number;
  text: string;
};

export type FileRangeResult = {
  lines: FileLine[];
  error: string | null;
  path?: string;
  duration_ms?: number;
};

export async function listFiles(path: string): Promise<FileListResult | null> {
  const { ok, data } = await safeFetch("/api/files/list", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!ok) return null; // caller treats null as "backend offline / unreachable"
  return data as FileListResult;
}

export async function readFileRange(path: string, start: number, end: number): Promise<FileRangeResult | null> {
  const { ok, data } = await safeFetch("/api/files/read-range", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, start, end }),
  });
  if (!ok) return null;
  return data as FileRangeResult;
}

// Back-compat aliases (kept in case other code still references the old names)
export const listFilesBridge = listFiles;
export const readFileRangeBridge = readFileRange;

// ─── QA Snapshot & Report (v3.2) ───────────────────────────────────────────

export type BridgeQASnapshot = {
  backend_ok: boolean;
  ollama_status: string;
  active_model: string;
  configured_models_count: number;
  patch_mode: string;
  allowed_roots: string[];
  safe_command_count: number;
  quick_timeout: number;
  balanced_timeout: number;
  detailed_timeout: number;
  timestamp: string;
  overall_status: string;
  duration_ms?: number;
};

export type BridgeQAReport = {
  report: string;
  overall_status: string;
  timestamp: string;
  duration_ms?: number;
};

export async function fetchQASnapshot(): Promise<BridgeQASnapshot | null> {
  const { ok, data } = await safeFetch("/api/qa/snapshot");
  return ok ? (data as BridgeQASnapshot) : null;
}

export async function fetchQAReport(): Promise<BridgeQAReport | null> {
  const { ok, data } = await safeFetch("/api/qa/report");
  return ok ? (data as BridgeQAReport) : null;
}

// ─── Memory Search & Indexing (v3.1 P5) ──────────────────────────────────────

export type MemoryReindexResponse = {
  indexed_files: number;
  indexed_chunks: number;
  skipped_files: number;
  embedding_available: boolean;
  retrieval_mode: string;
  duration_ms: number;
  errors: string[];
};

export type MemorySearchResult = {
  relative_path: string;
  chunk_id: number;
  snippet: string;
  score: number;
  base_score?: number;
  final_score?: number;
  source: "embedding" | "keyword";
  line_info: string;
  ranking_notes?: string[];
};

export type MemorySearchResponse = {
  query: string;
  retrieval_mode: string;
  embedding_error?: string | null;
  ranking_profile?: string;
  production_boost_applied?: boolean;
  test_downrank_applied?: boolean;
  query_boost_applied?: boolean;
  results: MemorySearchResult[];
};

export async function reindexMemory(model?: string): Promise<MemoryReindexResponse | null> {
  const url = model ? `/api/memory/reindex?model=${encodeURIComponent(model)}` : "/api/memory/reindex";
  const { ok, data } = await safeFetch(url, { method: "POST" });
  return ok ? (data as MemoryReindexResponse) : null;
}

export async function searchMemory(query: string, model?: string): Promise<MemorySearchResponse | null> {
  let url = `/api/memory/search?q=${encodeURIComponent(query)}`;
  if (model) {
    url += `&model=${encodeURIComponent(model)}`;
  }
  const { ok, data } = await safeFetch(url);
  return ok ? (data as MemorySearchResponse) : null;
}
