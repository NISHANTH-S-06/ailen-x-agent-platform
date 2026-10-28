"""
project_memory.py — Safe file discovery, relative path validation, and keyword text search.
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import urllib.request
import urllib.error
import json
import hashlib
import time
from agent_config import get_active_workspace, OLLAMA_BASE_URL
from agent_tools import is_blocked_filename, is_allowed_path, has_blocked_segment, check_ollama_status

IGNORED_DIRS = {
    ".git", "node_modules", "dist", "build", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", "coverage"
}

ALLOWED_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md",
    ".txt", ".css", ".html", ".yml", ".yaml", ".toml"
}


def is_secret_file_name(name: str) -> bool:
    """
    Check if file name contains sensitive terms (secret, token, key, password, credential)
    unless they are example or doc references.
    """
    low = name.lower()
    # Explicitly block known environment files
    if low in (".env", ".env.local", ".env.production", ".env.development", ".env.test", ".env.staging"):
        return True

    sensitive_words = ["secret", "token", "key", "password", "credential"]
    if any(w in low for w in sensitive_words):
        # Allow safe example, doc, template or spec patterns
        ok_words = ["example", "sample", "spec", "test", "doc", "tutorial", "guide", "readme", "mock"]
        if any(ok in low for ok in ok_words) or low.endswith(".env.example"):
            return False
        return True
    return False


def is_ignored_directory(path: Path) -> bool:
    """Return True if path is within any directory configured as ignored."""
    for part in path.parts:
        part_low = part.lower()
        if part in IGNORED_DIRS or "backup" in part_low:
            return True
    return False


def discover_project_files() -> List[Path]:
    """Safe scan of active workspace recursively. Restricts to code files <= 200 KB."""
    workspace = get_active_workspace()
    files = []
    
    for root, dirs, filenames in os.walk(workspace):
        root_path = Path(root)
        if is_ignored_directory(root_path):
            continue
            
        # Modify dirs in-place to skip scanning ignored folders
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and "backup" not in d.lower()]
        
        for fname in filenames:
            fpath = root_path / fname
            
            # Restrict file type
            ext = fpath.suffix.lower()
            if ext not in ALLOWED_EXTENSIONS and fname.lower() != ".env.example":
                continue
                
            # Restrict secrets and blocks
            if is_blocked_filename(fpath):
                continue
            if is_secret_file_name(fname):
                continue
            if not is_allowed_path(fpath):
                continue
                
            # Restrict file size (max 200 KB)
            try:
                if fpath.stat().st_size > 200 * 1024:
                    continue
            except Exception:
                continue
                
            files.append(fpath)
            
    return files


def safe_resolve_relative(rel_path: str) -> Tuple[Optional[Path], Optional[str]]:
    """
    Resolve and validate workspace-relative path safely.
    Returns (Path, None) on success or (None, error_msg) on failure.
    """
    workspace = get_active_workspace()
    
    # Clean traversal characters
    cleaned = rel_path.strip().strip('"').strip("'").replace("\\", "/")
    
    # Construct target candidate
    candidate = (workspace / cleaned).resolve()
    
    # Path traversal check
    try:
        candidate.relative_to(workspace)
    except ValueError:
        return None, f"🚫 BLOCKED: Path traversal detected - '{rel_path}' resolves outside active workspace."
        
    # Re-apply P0 validation checks
    if has_blocked_segment(str(candidate)):
        return None, f"🚫 BLOCKED: Path contains a blocked segment."
        
    if is_blocked_filename(candidate):
        return None, f"🔒 BLOCKED: '{candidate.name}' is a protected file and cannot be read."
        
    if not is_allowed_path(candidate):
        return None, f"🚫 BLOCKED: Path is outside allowed roots."
        
    return candidate, None


def search_project_memory(query: str) -> List[Dict[str, Any]]:
    """Lightweight text matching over discovered safe files. Limits results to top 20."""
    query_low = query.lower().strip()
    if not query_low:
        return []
        
    discovered = discover_project_files()
    results = []
    
    for fpath in discovered:
        rel_path = fpath.relative_to(get_active_workspace())
        rel_path_str = str(rel_path).replace("\\", "/")
        file_name = fpath.name
        
        score = 0
        matched_lines = []
        
        # Scoring logic
        if query_low == file_name.lower():
            score += 100
        elif query_low in file_name.lower():
            score += 50
            
        if query_low in rel_path_str.lower():
            score += 20
            
        # Try simple content search
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            matches = 0
            for idx, line in enumerate(lines):
                if query_low in line.lower():
                    matches += 1
                    if len(matched_lines) < 3:
                        matched_lines.append({
                            "line": idx + 1,
                            "text": line.strip()
                        })
            if matches > 0:
                score += min(30, matches * 5)
        except Exception:
            pass
            
        if score > 0:
            snippet = ""
            if matched_lines:
                snippet = "\n".join(f"L{item['line']}: {item['text']}" for item in matched_lines)
            else:
                snippet = "(Filename match)"
                
            try:
                size_bytes = fpath.stat().st_size
            except Exception:
                size_bytes = 0
                
            results.append({
                "relative_path": rel_path_str,
                "file_name": file_name,
                "extension": fpath.suffix,
                "matched_lines": matched_lines,
                "snippet": snippet,
                "score": score,
                "size_bytes": size_bytes,
                "safe_to_read": True
            })
            
    # Sort and limit
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:20]


def get_ollama_embedding(text: str, model: str = "nomic-embed-text") -> Tuple[Optional[List[float]], Optional[str]]:
    """Get embedding vector from local Ollama instance."""
    try:
        running, found, msg = check_ollama_status(model)
        if not running:
            return None, f"Ollama is not running. {msg}"
        if not found:
            return None, f"Model '{model}' is not available in Ollama."
    except Exception as exc:
        return None, f"Error checking model status: {exc}"

    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {
        "model": model,
        "prompt": text
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as res:
            resp_data = json.loads(res.read().decode("utf-8"))
            emb = resp_data.get("embedding")
            if not emb:
                return None, "No 'embedding' key found in Ollama response."
            return emb, None
    except TimeoutError:
        return None, "Ollama request timed out."
    except urllib.error.URLError as exc:
        return None, f"Ollama connection error: {exc.reason}"
    except Exception as exc:
        return None, f"Error calling Ollama: {exc}"


def get_index_path() -> Path:
    workspace = get_active_workspace()
    return workspace / ".agent_memory" / "index.json"


def chunk_file_text(text: str, rel_path_str: str, chunk_size: int = 2000, overlap: int = 200) -> List[Dict[str, Any]]:
    """
    Split file text into overlapping chunks of size `chunk_size` characters, with `overlap` characters.
    Each chunk is prefixed with the file relative path.
    """
    if not text or not text.strip():
        return []
    
    chunks = []
    start = 0
    length = len(text)
    chunk_id = 0
    
    while start < length:
        end = min(start + chunk_size, length)
        chunk_content = text[start:end]
        
        if chunk_content.strip():
            labeled_text = f"File: {rel_path_str}\n\n{chunk_content}"
            chunks.append({
                "chunk_id": chunk_id,
                "chunk_text": labeled_text
            })
            chunk_id += 1
            
        if end == length:
            break
        start += chunk_size - overlap
        
    return chunks


def reindex_project_memory(model: str = "nomic-embed-text") -> Dict[str, Any]:
    """
    Scan workspace files. Compute hashes/mtime to check for updates.
    Generate chunks and retrieve embeddings from Ollama for modified/new files.
    Caps total chunks in the index to 1000 chunks.
    """
    t0 = time.monotonic()
    index_path = get_index_path()
    
    old_index = {}
    if index_path.exists():
        try:
            old_index = json.loads(index_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            pass
            
    files_dict = old_index.get("files", {})
    new_files_dict = {}
    
    discovered = discover_project_files()
    
    indexed_files_count = 0
    indexed_chunks_count = 0
    skipped_files_count = 0
    
    embedding_available = False
    emb_err = None
    try:
        running, found, msg = check_ollama_status(model)
        if running and found:
            embedding_available = True
        else:
            emb_err = f"Model '{model}' is not available."
    except Exception as exc:
        emb_err = str(exc)
        
    retrieval_mode = "embedding" if embedding_available else "keyword"
    errors = []
    
    total_chunks_acc = 0
    
    for fpath in discovered:
        if total_chunks_acc >= 1000:
            skipped_files_count += 1
            continue
            
        rel_path = fpath.relative_to(get_active_workspace())
        rel_path_str = str(rel_path).replace("\\", "/")
        
        try:
            stat = fpath.stat()
            mtime = stat.st_mtime
            size = stat.st_size
        except Exception as exc:
            errors.append(f"Stat failed for {rel_path_str}: {exc}")
            skipped_files_count += 1
            continue
            
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            errors.append(f"Read failed for {rel_path_str}: {exc}")
            skipped_files_count += 1
            continue
            
        content_hash = hashlib.md5(content.encode("utf-8", errors="ignore")).hexdigest()
        
        cached = files_dict.get(rel_path_str)
        if (cached and 
            cached.get("file_mtime") == mtime and 
            cached.get("file_size") == size and 
            cached.get("content_hash") == content_hash):
            cached_chunks = cached.get("chunks", [])
            if total_chunks_acc + len(cached_chunks) <= 1000:
                new_files_dict[rel_path_str] = cached
                total_chunks_acc += len(cached_chunks)
                indexed_files_count += 1
                indexed_chunks_count += len(cached_chunks)
                continue
            else: 
                skipped_files_count += 1
                continue
        
        file_chunks = chunk_file_text(content, rel_path_str)
        
        processed_chunks = []
        for chunk in file_chunks:
            if total_chunks_acc >= 1000:
                break
                
            vector = None
            if embedding_available:
                vector, err = get_ollama_embedding(chunk["chunk_text"], model)
                if err:
                    errors.append(f"Embedding failed for {rel_path_str} chunk {chunk['chunk_id']}: {err}")
                    
            processed_chunks.append({
                "chunk_id": chunk["chunk_id"],
                "chunk_text": chunk["chunk_text"],
                "embedding": vector
            })
            total_chunks_acc += 1
            
        if processed_chunks:
            new_files_dict[rel_path_str] = {
                "file_mtime": mtime,
                "file_size": size,
                "content_hash": content_hash,
                "chunks": processed_chunks
            }
            indexed_files_count += 1
            indexed_chunks_count += len(processed_chunks)
        else:
            skipped_files_count += 1
            
    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps({"files": new_files_dict}, indent=2), encoding="utf-8")
    except Exception as exc:
        errors.append(f"Failed to write index file: {exc}")
        
    duration_ms = int((time.monotonic() - t0) * 1000)
    
    return {
        "indexed_files": indexed_files_count,
        "indexed_chunks": indexed_chunks_count,
        "skipped_files": skipped_files_count,
        "embedding_available": embedding_available,
        "retrieval_mode": retrieval_mode,
        "duration_ms": duration_ms,
        "errors": errors[:5]
    }


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(x * y for x, y in zip(v1, v2))
    norm_v1 = sum(x * x for x in v1) ** 0.5
    norm_v2 = sum(y * y for y in v2) ** 0.5
    if norm_v1 * norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)


def keyword_score_chunk(query_low: str, rel_path: str, chunk_text: str) -> float:
    score = 0.0
    filename = rel_path.split("/")[-1]
    if query_low == filename.lower():
        score += 100.0
    elif query_low in filename.lower():
        score += 50.0
    if query_low in rel_path.lower():
        score += 20.0
    
    occurrences = chunk_text.lower().count(query_low)
    if occurrences > 0:
        score += min(30.0, occurrences * 5.0)
    return score


PRODUCTION_SOURCE_BOOSTS = {
    "backend_bridge.py": 22.0,
    "project_memory.py": 22.0,
    "agent_tools.py": 18.0,
    "agent_config.py": 18.0,
    "frontend/src/App.tsx": 18.0,
    "frontend/src/apiClient.ts": 16.0,
    "frontend/src/types.ts": 14.0,
}

TEST_QUERY_TERMS = [
    "test", "tests", "pytest", "unit test", "test case",
    "coverage", "failing test", "assertion", "test_safety"
]


def is_test_file_path(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").lower().split("/")
    filename = parts[-1]
    return (
        filename.startswith("test_")
        or filename.endswith("_test.py")
        or filename == "test_safety.py"
        or "tests" in parts
    )


def is_test_related_query(query_low: str) -> bool:
    return any(term in query_low for term in TEST_QUERY_TERMS)


def query_boost_for_path(query_low: str, rel_path: str, chunk_text: str) -> Tuple[float, List[str]]:
    rel = rel_path.replace("\\", "/")
    notes: List[str] = []
    boost = 0.0
    haystack = f"{rel.lower()}\n{chunk_text.lower()}"

    if is_test_related_query(query_low):
        filename = rel.split("/")[-1].lower()
        stem = filename.rsplit(".", 1)[0]
        if filename in query_low or stem in query_low:
            boost += 45.0
            notes.append("test_query_target")

    model_router_terms = [
        "model router", "route model", "select_model", "select_model_for_prompt",
        "resolved_model", "selected_model", "qwen", "gemma", "llama", "agent-aline-x"
    ]
    memory_terms = [
        "memory search", "project memory", "retrieval", "embedding", "reindex",
        "index", "chunk", "search_memory", "project_memory"
    ]
    safety_terms = [
        "safe path", "allowed path", "workspace", "traversal",
        "blocked path", "command safety"
    ]
    frontend_terms = [
        "ui", "frontend", "badge", "context count", "selected files",
        "react", "vite", "typescript"
    ]

    if any(term in query_low for term in model_router_terms):
        if rel == "backend_bridge.py":
            boost += 34.0
            notes.append("model_router_core")
        elif rel == "agent_tools.py" and any(term in haystack for term in ("ollama", "model", "chat")):
            boost += 16.0
            notes.append("model_router_ollama")
        elif rel == "project_memory.py" and any(term in query_low for term in ("memory", "search", "retrieval")):
            boost += 10.0
            notes.append("model_router_memory_context")

    if any(term in query_low for term in memory_terms):
        if rel == "project_memory.py":
            boost += 34.0
            notes.append("memory_core")
        elif rel == "backend_bridge.py":
            boost += 16.0
            notes.append("memory_api_chat")

    if any(term in query_low for term in safety_terms):
        if rel == "agent_tools.py":
            boost += 30.0
            notes.append("safety_core")
        elif rel == "agent_config.py":
            boost += 30.0
            notes.append("workspace_config_core")
        elif rel == "backend_bridge.py":
            boost += 14.0
            notes.append("safety_api")

    if any(term in query_low for term in frontend_terms):
        if rel == "frontend/src/App.tsx":
            boost += 30.0
            notes.append("frontend_core")
        elif rel == "frontend/src/apiClient.ts":
            boost += 18.0
            notes.append("frontend_api_client")
        elif rel == "frontend/src/types.ts":
            boost += 16.0
            notes.append("frontend_types")

    return boost, notes


def apply_ranking_adjustments(query_low: str, rel_path: str, chunk_text: str, base_score: float) -> Tuple[float, List[str]]:
    notes: List[str] = []
    final_score = base_score

    prod_boost = PRODUCTION_SOURCE_BOOSTS.get(rel_path.replace("\\", "/"), 0.0)
    if prod_boost:
        final_score += prod_boost
        notes.append("production_boost")

    if is_test_file_path(rel_path) and not is_test_related_query(query_low):
        final_score -= 32.0
        notes.append("test_downrank")

    query_boost, query_notes = query_boost_for_path(query_low, rel_path, chunk_text)
    if query_boost:
        final_score += query_boost
        notes.extend(query_notes)

    return max(0.01, final_score), notes


def search_memory_index(query: str, limit: int = 10, model: str = "nomic-embed-text") -> Dict[str, Any]:
    """Search local memory index using Hybrid ranking or Keyword Fallback."""
    query_low = query.lower().strip()
    if not query_low:
        return {
            "query": query,
            "retrieval_mode": "none",
            "ranking_profile": "production_first",
            "production_boost_applied": False,
            "test_downrank_applied": False,
            "query_boost_applied": False,
            "results": []
        }
        
    index_path = get_index_path()
    if not index_path.exists():
        return {
            "query": query,
            "retrieval_mode": "keyword_fallback (no index)",
            "ranking_profile": "production_first",
            "production_boost_applied": False,
            "test_downrank_applied": False,
            "query_boost_applied": False,
            "results": []
        }
        
    try:
        index_data = json.loads(index_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception as exc:
        return {
            "query": query,
            "retrieval_mode": f"error: {exc}",
            "ranking_profile": "production_first",
            "production_boost_applied": False,
            "test_downrank_applied": False,
            "query_boost_applied": False,
            "results": []
        }
        
    files_dict = index_data.get("files", {})
    
    query_vector = None
    embedding_available = False
    emb_err = None
    
    try:
        running, found, msg = check_ollama_status(model)
        if running and found:
            query_vector, emb_err = get_ollama_embedding(query, model)
            if query_vector:
                embedding_available = True
            else:
                emb_err = f"Failed to generate query embedding: {emb_err}"
        else:
            if not running:
                emb_err = None  # Ollama not running -> expected keyword fallback
            else:
                emb_err = f"Model '{model}' not found in Ollama."
    except Exception as exc:
        emb_err = f"Error checking embedding availability: {exc}"
        
    retrieval_mode = "embedding" if embedding_available else "keyword"
    if emb_err and not embedding_available:
        retrieval_mode = "hybrid_fallback"
        
    results = []
    production_boost_applied = False
    test_downrank_applied = False
    query_boost_applied = False
    
    for rel_path_str, file_info in files_dict.items():
        chunks = file_info.get("chunks", [])
        filename = rel_path_str.split("/")[-1]
        
        for chunk in chunks:
            chunk_text = chunk.get("chunk_text", "")
            chunk_id = chunk.get("chunk_id", 0)
            chunk_emb = chunk.get("embedding")
            
            score = 0.0
            source = "keyword"
            
            if embedding_available and chunk_emb and query_vector:
                similarity = cosine_similarity(query_vector, chunk_emb)
                score = similarity * 100.0
                source = "embedding"
                
                if query_low == filename.lower():
                    score += 20.0
                elif query_low in filename.lower():
                    score += 10.0
                if query_low in rel_path_str.lower():
                    score += 5.0
                    
                if query_low in chunk_text.lower():
                    score += 30.0
            else:
                score = keyword_score_chunk(query_low, rel_path_str, chunk_text)
                source = "keyword"
                
            if score > 0:
                base_score = score
                final_score, ranking_notes = apply_ranking_adjustments(query_low, rel_path_str, chunk_text, base_score)
                production_boost_applied = production_boost_applied or "production_boost" in ranking_notes
                test_downrank_applied = test_downrank_applied or "test_downrank" in ranking_notes
                query_boost_applied = query_boost_applied or any(note not in ("production_boost", "test_downrank") for note in ranking_notes)
                results.append({
                    "relative_path": rel_path_str,
                    "chunk_id": chunk_id,
                    "snippet": chunk_text,
                    "score": round(final_score, 2),
                    "base_score": round(base_score, 2),
                    "final_score": round(final_score, 2),
                    "source": source,
                    "line_info": f"Chunk {chunk_id}",
                    "ranking_notes": ranking_notes
                })
                
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:limit]
    
    return {
        "query": query,
        "retrieval_mode": retrieval_mode,
        "embedding_error": emb_err,
        "ranking_profile": "production_first",
        "production_boost_applied": production_boost_applied,
        "test_downrank_applied": test_downrank_applied,
        "query_boost_applied": query_boost_applied,
        "results": results
    }
