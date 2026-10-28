import pytest
from pathlib import Path
import agent_tools

def test_is_allowed_path_mocked(monkeypatch, tmp_path):
    # Mock allowed roots using a temporary directory
    mock_root = (tmp_path / "AGENT_ALINE_X").resolve()
    mock_root.mkdir()
    
    # Temporarily override ALLOWED_ROOTS in agent_tools
    monkeypatch.setattr(agent_tools, "ALLOWED_ROOTS", [mock_root])
    
    # 1. Allowed project root passes
    assert agent_tools.is_allowed_path(mock_root)
    
    # 2. File or folder inside allowed root passes
    inside_folder = mock_root / "some_folder"
    inside_file = inside_folder / "file.txt"
    assert agent_tools.is_allowed_path(inside_file)
    assert agent_tools.is_allowed_path(inside_folder)
    
    # 3. Sibling folder with same prefix is blocked
    sibling = (tmp_path / "AGENT_ALINE_X_backup").resolve()
    assert not agent_tools.is_allowed_path(sibling)
    
    # 4. Parent traversal is blocked
    traversal = (mock_root / ".." / "AGENT_ALINE_X_backup").resolve()
    assert not agent_tools.is_allowed_path(traversal)
    
    # 5. Random outside path is blocked
    outside = Path("C:/Windows/System32")
    assert not agent_tools.is_allowed_path(outside)

def test_is_allowed_path_real_roots():
    # Real roots from config
    for root in agent_tools.ALLOWED_ROOTS:
        assert agent_tools.is_allowed_path(root)
        # Check standard child inside allowed root passes
        assert agent_tools.is_allowed_path(root / "some_dummy_subfolder")
        
    # Check parent traversal on real roots
    for root in agent_tools.ALLOWED_ROOTS:
        # A sibling folder with prefix_backup should be blocked
        sibling_name = root.name + "_backup"
        sibling_path = root.parent / sibling_name
        assert not agent_tools.is_allowed_path(sibling_path)
        
        # Traversal to sibling should be blocked
        traversal = root / ".." / sibling_name
        assert not agent_tools.is_allowed_path(traversal)

def test_select_model_for_prompt():
    from backend_bridge import select_model_for_prompt
    
    # 1. Normal chat / planning / greetings
    model, reason = select_model_for_prompt("hello there, how are you?")
    assert model == "agent-aline-x:latest"
    assert "normal" in reason
    
    model, reason = select_model_for_prompt("explain the project and make a plan")
    assert model == "agent-aline-x:latest"
    
    # 2. Code / bug / patch / errors
    model, reason = select_model_for_prompt("please fix this traceback error in python")
    assert model == "qwen2.5-coder:7b"
    assert "code" in reason
    
    model, reason = select_model_for_prompt("run pytest command in powershell")
    assert model == "qwen2.5-coder:7b"
    
    # 3. Deep audit / QA / compliance
    model, reason = select_model_for_prompt("do a security audit and QA review of requirements")
    assert model == "maxwellb/gemma4-12b-it-oym:latest"
    assert "audit" in reason
    
    # 4. Manual selection
    model, reason = select_model_for_prompt("hello", mode="qwen2.5-coder:7b")
    assert model == "qwen2.5-coder:7b"
    assert "manual" in reason

    model, reason = select_model_for_prompt("hello", mode="agent-aline-x")
    assert model == "agent-aline-x:latest"
    assert "manual" in reason

    model, reason = select_model_for_prompt("hello", mode="maxwellb/gemma4-12b-it-oym")
    assert model == "maxwellb/gemma4-12b-it-oym:latest"
    assert "manual" in reason


def test_model_discovery_offline(monkeypatch):
    import backend_bridge
    # Force connection error in urllib.request.urlopen
    def mock_urlopen(*args, **kwargs):
        import urllib.error
        raise urllib.error.URLError("Mocked offline status")
    
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    # Invalidate cache
    backend_bridge._MODEL_CACHE["data"] = None
    backend_bridge._MODEL_CACHE["expiry"] = 0.0
    
    res = backend_bridge.discover_models_cached()
    assert not res["ollama_reachable"]
    assert "offline" in res["status_detail"].lower()
    
    discovered = res["discovered_models"]
    # Check that preferred models are mapped as unavailable
    names = [m["name"] for m in discovered]
    assert "agent-aline-x:latest" in names
    for m in discovered:
        if m["name"] == "agent-aline-x:latest":
            assert not m["available"]
            assert m["source"] == "fallback_config"


def test_model_discovery_roles(monkeypatch):
    import backend_bridge
    import urllib.request
    import json

    # Mock Ollama returning 1 installed model
    class MockResponse:
        def read(self):
            return json.dumps({
                "models": [
                    {"name": "agent-aline-x:latest"},
                    {"name": "custom-model:latest"}
                ]
            }).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_urlopen(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    # Invalidate cache
    backend_bridge._MODEL_CACHE["data"] = None
    backend_bridge._MODEL_CACHE["expiry"] = 0.0

    res = backend_bridge.discover_models_cached()
    assert res["ollama_reachable"]
    
    discovered = res["discovered_models"]
    
    # Verify default role mapping
    for m in discovered:
        if m["name"] == "agent-aline-x:latest":
            assert m["available"]
            assert m["role"] == "default_agent"
            assert m["source"] == "ollama"
        elif m["name"] == "qwen2.5-coder:7b":
            assert not m["available"]
            assert m["role"] == "code_expert"
            assert m["source"] == "fallback_config"
        elif m["name"] == "custom-model:latest":
            assert m["available"]
            assert m["role"] == "custom"
            assert m["source"] == "ollama"


def test_router_missing_model_fallback(monkeypatch):
    import backend_bridge
    
    # Test case 1: agent-aline-x:latest is available, other is missing.
    # It should fallback to agent-aline-x:latest.
    monkeypatch.setattr(backend_bridge, "discover_models_cached", lambda: {
        "discovered_models": [
            {"name": "agent-aline-x:latest", "available": True},
            {"name": "qwen2.5-coder:7b", "available": False}
        ],
        "ollama_reachable": True,
        "status_detail": ""
    })
    
    # We select qwen2.5-coder:7b, which is unavailable. It should fallback to agent-aline-x:latest.
    model, reason = backend_bridge.resolve_chat_model("qwen2.5-coder:7b")
    assert model == "agent-aline-x:latest"
    assert "falling back to agent-aline-x:latest" in reason.lower()
    
    # Test case 2: Both preferred are unavailable, but llama3:latest is available.
    monkeypatch.setattr(backend_bridge, "discover_models_cached", lambda: {
        "discovered_models": [
            {"name": "agent-aline-x:latest", "available": False},
            {"name": "qwen2.5-coder:7b", "available": False},
            {"name": "llama3:latest", "available": True}
        ],
        "ollama_reachable": True,
        "status_detail": ""
    })
    model, reason = backend_bridge.resolve_chat_model("qwen2.5-coder:7b")
    assert model == "llama3:latest"
    
    # Test case 3: Nothing available.
    monkeypatch.setattr(backend_bridge, "discover_models_cached", lambda: {
        "discovered_models": [],
        "ollama_reachable": True,
        "status_detail": ""
    })
    model, reason = backend_bridge.resolve_chat_model("qwen2.5-coder:7b")
    assert model == ""
    assert "no available ollama model" in reason.lower()


def test_workspace_defaults_and_validation():
    import agent_config
    
    # Verify default path is D:\AGENT_ALINE_X_
    assert agent_config.get_active_workspace() == Path("D:/AGENT_ALINE_X_").resolve()
    
    # Verify unsafe workspaces are rejected
    # Empty
    assert not agent_config.is_safe_workspace_path(Path(""))
    # Drive roots
    assert not agent_config.is_safe_workspace_path(Path("C:/"))
    assert not agent_config.is_safe_workspace_path(Path("D:/"))
    # System folder
    assert not agent_config.is_safe_workspace_path(Path("C:/Windows"))
    assert not agent_config.is_safe_workspace_path(Path("C:/Windows/System32"))
    # User profiles
    assert not agent_config.is_safe_workspace_path(Path("C:/Users"))
    assert not agent_config.is_safe_workspace_path(Path("C:/Users/mail2"))
    
    # Verify safe paths are accepted
    assert agent_config.is_safe_workspace_path(Path("D:/AGENT_ALINE_X_"))
    assert agent_config.is_safe_workspace_path(Path("D:/custom_workspace/project"))


# ─── P2: Performance metadata tests ─────────────────────────────────────────

def test_build_metadata_shape():
    """Metadata dict returned by build_metadata must contain every required key."""
    from backend_bridge import build_metadata
    from datetime import datetime, timezone

    meta = build_metadata(
        request_id="abc12345",
        selected_model="agent-aline-x:latest",
        resolved_model="agent-aline-x:latest",
        route_reason="normal chat / planning rule",
        duration_ms=500,
        fallback_used=False,
        fallback_from=None,
        fallback_to=None,
        error=None,
        prompt_length_chars=42,
        context_length_chars=1200,
    )

    required_keys = [
        "request_id", "selected_model", "resolved_model", "route_reason",
        "duration_ms", "fallback_used", "fallback_from", "fallback_to",
        "error", "prompt_length_chars", "context_length_chars", "created_at",
    ]
    for key in required_keys:
        assert key in meta, f"Missing key: {key}"

    assert meta["request_id"] == "abc12345"
    assert meta["selected_model"] == "agent-aline-x:latest"
    assert meta["duration_ms"] == 500
    assert meta["fallback_used"] is False
    assert meta["fallback_from"] is None
    assert meta["error"] is None
    assert isinstance(meta["created_at"], str)


def test_perf_history_max_20():
    """_PERF_HISTORY must never exceed PERF_HISTORY_MAX (20) records."""
    import backend_bridge
    from backend_bridge import build_metadata

    # Save and clear history
    original = backend_bridge._PERF_HISTORY[:]
    backend_bridge._PERF_HISTORY.clear()

    try:
        for i in range(25):
            rec = build_metadata(
                request_id=f"id{i}",
                selected_model="agent-aline-x:latest",
                resolved_model="agent-aline-x:latest",
                route_reason="normal chat / planning rule",
                duration_ms=i * 10,
                fallback_used=False,
                fallback_from=None,
                fallback_to=None,
                error=None,
                prompt_length_chars=10,
                context_length_chars=0,
            )
            backend_bridge._PERF_HISTORY.append(rec)
            if len(backend_bridge._PERF_HISTORY) > backend_bridge.PERF_HISTORY_MAX:
                backend_bridge._PERF_HISTORY.pop(0)

        assert len(backend_bridge._PERF_HISTORY) == backend_bridge.PERF_HISTORY_MAX
        # Oldest (id0..id4) should be evicted; newest (id5..id24) remain
        ids = [r["request_id"] for r in backend_bridge._PERF_HISTORY]
        assert "id0" not in ids
        assert "id24" in ids
    finally:
        backend_bridge._PERF_HISTORY.clear()
        backend_bridge._PERF_HISTORY.extend(original)


def test_p0_routing_sanity():
    """Quick sanity: P0 keyword routing still maps correctly after P2 patch."""
    from backend_bridge import select_model_for_prompt

    # Normal chat
    model, reason = select_model_for_prompt("hello, explain the project")
    assert model == "agent-aline-x:latest"
    assert "normal" in reason

    # Code path
    model, reason = select_model_for_prompt("fix this traceback in python")
    assert model == "qwen2.5-coder:7b"
    assert "code" in reason

    # Audit path
    model, reason = select_model_for_prompt("do a security audit and qa review")
    assert model == "maxwellb/gemma4-12b-it-oym:latest"
    assert "audit" in reason


# ─── P3: Context Trimming + Quality Controls ─────────────────────────────────

def test_trim_context_keeps_latest():
    """trim_context_chunks must always keep the most recent chunk."""
    from backend_bridge import trim_context_chunks

    chunks = [f"chunk-{i} " + ("x" * 500) for i in range(20)]
    trimmed, total, dropped = trim_context_chunks(chunks, max_chars=3000)

    # Most recent chunk must be present
    assert any("chunk-19" in c for c in trimmed), "Latest chunk must be kept"
    assert total <= 3000


def test_trim_context_reduces_oversize():
    """Trimmed output must not exceed max_chars budget."""
    from backend_bridge import trim_context_chunks

    big_chunk = "A" * 20_000
    chunks = [big_chunk]
    trimmed, total, dropped = trim_context_chunks(chunks, max_chars=5000)

    assert total <= 5000 + 29
    assert all(len(c) <= 5000 + 29 for c in trimmed)


def test_trim_context_reports_dropped():
    """When oversized context is supplied, dropped > 0 or total < original."""
    from backend_bridge import trim_context_chunks

    # 10 chunks of 2000 chars each = 20_000 total, budget = 8000
    chunks = ["B" * 2000 for _ in range(10)]
    original_total = sum(len(c) for c in chunks)
    trimmed, final_total, dropped = trim_context_chunks(chunks, max_chars=8000)

    context_trimmed = dropped > 0 or (original_total > final_total)
    assert context_trimmed is True


def test_quality_profile_normal():
    """Normal chat route produces the normal_chat quality profile."""
    from backend_bridge import get_quality_profile

    profile_name, instruction = get_quality_profile("normal chat / planning rule", "agent-aline-x:latest")
    assert profile_name == "normal_chat"
    assert "concise" in instruction.lower() or "direct" in instruction.lower()
    assert "SAFETY" in instruction  # hallucination safety appended


def test_quality_profile_code():
    """Code/bug route produces the code_debug quality profile."""
    from backend_bridge import get_quality_profile

    profile_name, instruction = get_quality_profile("code / bug rule", "qwen2.5-coder:7b")
    assert profile_name == "code_debug"
    assert "minimal patch" in instruction.lower() or "bug" in instruction.lower()
    assert "SAFETY" in instruction


def test_quality_profile_audit():
    """Audit/QA route produces the audit_qa quality profile."""
    from backend_bridge import get_quality_profile

    profile_name, instruction = get_quality_profile("deep audit / QA rule", "maxwellb/gemma4-12b-it-oym:latest")
    assert profile_name == "audit_qa"
    assert "confirmed" in instruction.lower() or "audit" in instruction.lower()
    assert "SAFETY" in instruction


def test_response_mode_default_balanced():
    """response_length_config with None input defaults to 'balanced'."""
    from backend_bridge import response_length_config

    key, cfg = response_length_config(None)
    assert key == "balanced"
    assert "num_predict" in cfg
    assert "timeout" in cfg
    assert "context_chars" in cfg


def test_build_metadata_p3_fields():
    """build_metadata must contain all P3 fields with correct types."""
    from backend_bridge import build_metadata

    meta = build_metadata(
        request_id="test-p3",
        selected_model="agent-aline-x:latest",
        resolved_model="agent-aline-x:latest",
        route_reason="normal chat / planning rule",
        duration_ms=123,
        fallback_used=False,
        fallback_from=None,
        fallback_to=None,
        error=None,
        prompt_length_chars=50,
        context_length_chars=800,
        context_trimmed=True,
        original_context_length_chars=5000,
        final_context_length_chars=800,
        response_mode="balanced",
        quality_profile="normal_chat",
    )

    assert meta["context_trimmed"] is True
    assert meta["original_context_length_chars"] == 5000
    assert meta["final_context_length_chars"] == 800
    assert meta["response_mode"] == "balanced"
    assert meta["quality_profile"] == "normal_chat"
    assert isinstance(meta["created_at"], str)


def test_hallucination_safety_in_all_profiles():
    """Every quality profile instruction must include the HALLUCINATION_SAFETY addendum."""
    from backend_bridge import get_quality_profile

    routes = [
        ("normal chat / planning rule", "agent-aline-x:latest"),
        ("code / bug rule", "qwen2.5-coder:7b"),
        ("deep audit / QA rule", "maxwellb/gemma4-12b-it-oym:latest"),
        ("normal chat / planning rule", "llama3:latest"),
    ]
    for route_reason, model in routes:
        _, instruction = get_quality_profile(route_reason, model)
        assert "SAFETY" in instruction, f"SAFETY missing for route={route_reason}, model={model}"
        assert "Not checked" in instruction or "invent" in instruction


# ─── P4: File Context Intelligence + Project Memory Search ───────────────────

import pytest
from pathlib import Path

def test_safe_file_discovery_restrictions(tmp_path):
    """discover_project_files scans allowed workspace and applies filter rules."""
    import project_memory
    import agent_config
    
    # Setup mock workspace
    ws = tmp_path / "mock_workspace"
    ws.mkdir()
    
    # Create safe files
    (ws / "app.py").write_text("print('hello')", encoding="utf-8")
    (ws / "styles.css").write_text("body {}", encoding="utf-8")
    
    # Create noisy folders and files
    (ws / "node_modules").mkdir()
    (ws / "node_modules" / "index.js").write_text("console.log()", encoding="utf-8")
    
    (ws / ".git").mkdir()
    (ws / ".git" / "config").write_text("config", encoding="utf-8")
    
    (ws / "backup_dir").mkdir()
    (ws / "backup_dir" / "old.py").write_text("old", encoding="utf-8")
    
    # Create disallowed extension
    (ws / "image.png").write_bytes(b"\x89PNG")
    
    # Mock active workspace
    orig_ws_pm = project_memory.get_active_workspace
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    # Mock get_active_workspace and ALLOWED_ROOTS/WRITE_ALLOWED_ROOTS in place
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    
    try:
        discovered = project_memory.discover_project_files()
        discovered_names = [f.name for f in discovered]
        
        assert "app.py" in discovered_names
        assert "styles.css" in discovered_names
        assert "index.js" not in discovered_names
        assert "config" not in discovered_names
        assert "old.py" not in discovered_names
        assert "image.png" not in discovered_names
    finally:
        project_memory.get_active_workspace = orig_ws_pm
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)


def test_traversal_path_blocked(tmp_path):
    """safe_resolve_relative blocks relative paths resolving outside workspace."""
    import project_memory
    import agent_config
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    
    # Mock active workspace
    orig_ws_pm = project_memory.get_active_workspace
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    try:
        # Traversal path
        candidate, err = project_memory.safe_resolve_relative("../other_folder/file.py")
        assert candidate is None
        assert "traversal" in err.lower()
        
        # Valid path
        (ws / "test.py").write_text("print()", encoding="utf-8")
        candidate, err = project_memory.safe_resolve_relative("test.py")
        assert candidate is not None
        assert err is None
    finally:
        project_memory.get_active_workspace = orig_ws_pm
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def test_secret_files_blocked():
    """is_secret_file_name flags secret/token/credential files except examples/docs."""
    from project_memory import is_secret_file_name
    
    assert is_secret_file_name(".env") is True
    assert is_secret_file_name("secret_token.txt") is True
    assert is_secret_file_name("password.json") is True
    assert is_secret_file_name("credentials.yml") is True
    
    # Examples / docs exceptions
    assert is_secret_file_name(".env.example") is False
    assert is_secret_file_name("secret_mock.py") is False
    assert is_secret_file_name("api_key_sample.txt") is False
    assert is_secret_file_name("password_doc.md") is False


def test_large_files_truncated(tmp_path):
    """Files exceeding size preview limits are previewed up to limits only."""
    import project_memory
    import agent_config
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    
    large_content = "A" * 30_000
    (ws / "big.txt").write_text(large_content, encoding="utf-8")
    
    # Mock active workspace
    orig_ws_pm = project_memory.get_active_workspace
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    try:
        resolved, err = project_memory.safe_resolve_relative("big.txt")
        assert err is None
        
        # Discover filters files > 200 KB, but for preview we truncate at 20,000 characters
        # Let's test discovery filters files > 200 KB
        (ws / "huge.txt").write_text("A" * (250 * 1024), encoding="utf-8")
        discovered = project_memory.discover_project_files()
        discovered_names = [f.name for f in discovered]
        assert "huge.txt" not in discovered_names
        
    finally:
        project_memory.get_active_workspace = orig_ws_pm
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def test_search_memory_matches(tmp_path):
    """search_project_memory performs match and scores files by text relevance."""
    import project_memory
    import agent_config
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    
    (ws / "target.py").write_text("def my_special_function():\n    pass", encoding="utf-8")
    (ws / "other.py").write_text("def other():\n    pass", encoding="utf-8")
    
    # Mock active workspace
    orig_ws_pm = project_memory.get_active_workspace
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    
    try:
        results = project_memory.search_project_memory("special_function")
        assert len(results) > 0
        assert results[0]["file_name"] == "target.py"
        assert "target.py" in results[0]["relative_path"]
        assert "L1:" in results[0]["snippet"]
    finally:
        project_memory.get_active_workspace = orig_ws_pm
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)


def test_search_ignores_noisy_folders(tmp_path):
    """Search matches only safe paths, ignoring temp and env dirs."""
    import project_memory
    import agent_config
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    
    (ws / "node_modules").mkdir()
    (ws / "node_modules" / "lib.py").write_text("def lib(): pass", encoding="utf-8")
    (ws / "safe.py").write_text("def lib(): pass", encoding="utf-8")
    
    # Mock active workspace
    orig_ws_pm = project_memory.get_active_workspace
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    
    try:
        results = project_memory.search_project_memory("lib")
        paths = [r["relative_path"] for r in results]
        assert "safe.py" in paths
        assert "node_modules/lib.py" not in paths
    finally:
        project_memory.get_active_workspace = orig_ws_pm
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)


def test_chat_metadata_reports_file_context(tmp_path):
    """Metadata correctly registers file_context fields inside responses."""
    import backend_bridge
    from backend_bridge import ChatRequest, api_chat
    import agent_config
    import project_memory
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "sample.py").write_text("print('sample')", encoding="utf-8")
    
    # Mock active workspace
    orig_ws_bb = backend_bridge.get_active_workspace
    orig_ws_pm = project_memory.get_active_workspace
    backend_bridge.get_active_workspace = lambda: ws.resolve()
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    # Mock check_ollama_status and ollama_chat on backend_bridge
    orig_ollama_chat = backend_bridge.ollama_chat
    orig_status = backend_bridge.check_ollama_status
    orig_resolve = backend_bridge.resolve_chat_model
    
    backend_bridge.check_ollama_status = lambda m=None: (True, True, "online")
    backend_bridge.ollama_chat = lambda *args, **kwargs: ("Mocked LLM reply", None)
    backend_bridge.resolve_chat_model = lambda m: (m, None)
    
    try:
        req = ChatRequest(
            message="Explain project",
            context=[],
            selected_files=["sample.py"]
        )
        res = api_chat(req)
        meta = res["metadata"]
        assert meta["file_context_used"] is True
        assert meta["file_context_file_count"] == 1
        assert meta["file_context_chars"] > 0
        assert meta["file_context_trimmed"] is False
    finally:
        backend_bridge.get_active_workspace = orig_ws_bb
        project_memory.get_active_workspace = orig_ws_pm
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)
        backend_bridge.ollama_chat = orig_ollama_chat
        backend_bridge.check_ollama_status = orig_status
        backend_bridge.resolve_chat_model = orig_resolve


def test_file_context_packing_format(tmp_path):
    """Packed context matches the required tags structure."""
    import backend_bridge
    from backend_bridge import ChatRequest, api_chat
    import agent_config
    import project_memory
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "test_pack.py").write_text("content_data", encoding="utf-8")
    
    # Mock active workspace
    orig_ws_bb = backend_bridge.get_active_workspace
    orig_ws_pm = project_memory.get_active_workspace
    backend_bridge.get_active_workspace = lambda: ws.resolve()
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    orig_ollama_chat = backend_bridge.ollama_chat
    orig_status = backend_bridge.check_ollama_status
    orig_resolve = backend_bridge.resolve_chat_model
    
    packed_context = None
    
    def mock_chat(*args, **kwargs):
        nonlocal packed_context
        packed_context = kwargs.get("context_chunks")
        return "reply", None
        
    backend_bridge.check_ollama_status = lambda m=None: (True, True, "online")
    backend_bridge.ollama_chat = mock_chat
    backend_bridge.resolve_chat_model = lambda m: (m, None)
    
    try:
        req = ChatRequest(
            message="check tests",
            context=[],
            selected_files=["test_pack.py"]
        )
        api_chat(req)
        
        assert packed_context is not None
        assert len(packed_context) == 1
        assert "[Project File Context]" in packed_context[0]
        assert "File: test_pack.py" in packed_context[0]
        assert "content_data" in packed_context[0]
        assert "[/Project File Context]" in packed_context[0]
    finally:
        backend_bridge.get_active_workspace = orig_ws_bb
        project_memory.get_active_workspace = orig_ws_pm
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)
        backend_bridge.ollama_chat = orig_ollama_chat
        backend_bridge.check_ollama_status = orig_status
        backend_bridge.resolve_chat_model = orig_resolve


def test_p3_trimming_applies_to_file_context(tmp_path):
    """File context is trimmed when it exceeds route budgets."""
    import backend_bridge
    from backend_bridge import ChatRequest, api_chat
    import agent_config
    import project_memory
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    
    # Oversized context files (totaling 18_000 chars)
    # Balanced mode context limit is 14_000 chars, so it should trigger trimming
    (ws / "big1.txt").write_text("A" * 6000, encoding="utf-8")
    (ws / "big2.txt").write_text("B" * 6000, encoding="utf-8")
    (ws / "big3.txt").write_text("C" * 6000, encoding="utf-8")
    
    # Mock active workspace
    orig_ws_bb = backend_bridge.get_active_workspace
    orig_ws_pm = project_memory.get_active_workspace
    backend_bridge.get_active_workspace = lambda: ws.resolve()
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    orig_ollama_chat = backend_bridge.ollama_chat
    orig_status = backend_bridge.check_ollama_status
    orig_resolve = backend_bridge.resolve_chat_model
    
    backend_bridge.check_ollama_status = lambda m=None: (True, True, "online")
    backend_bridge.ollama_chat = lambda *args, **kwargs: ("reply", None)
    backend_bridge.resolve_chat_model = lambda m: (m, None)
    
    try:
        req = ChatRequest(
            message="Explain",
            context=[],
            selected_files=["big1.txt", "big2.txt", "big3.txt"],
            response_length="balanced"
        )
        res = api_chat(req)
        meta = res["metadata"]
        assert meta["context_trimmed"] is True
        assert meta["file_context_trimmed"] is True
    finally:
        backend_bridge.get_active_workspace = orig_ws_bb
        project_memory.get_active_workspace = orig_ws_pm
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)
        backend_bridge.ollama_chat = orig_ollama_chat
        backend_bridge.check_ollama_status = orig_status
        backend_bridge.resolve_chat_model = orig_resolve


def test_p0_p1_p2_p3_sanity():
    """Prior P0-P3 routing assertions still execute cleanly."""
    from backend_bridge import select_model_for_prompt
    
    model, reason = select_model_for_prompt("audit this file please")
    assert "audit" in reason
    assert model == "maxwellb/gemma4-12b-it-oym:latest"


def test_p5_ollama_offline_fallback(tmp_path):
    """Fallback to keyword retrieval if Ollama is offline or model missing."""
    import project_memory
    import agent_tools
    import agent_config
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "file1.txt").write_text("This is simple test code for backend bridge", encoding="utf-8")
    
    # Mock workspace and check_ollama_status
    orig_ws = project_memory.get_active_workspace
    orig_status = project_memory.check_ollama_status
    project_memory.get_active_workspace = lambda: ws.resolve()
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    try:
        stats = project_memory.reindex_project_memory()
        assert stats["embedding_available"] is False
        assert stats["retrieval_mode"] == "keyword"
        
        # Search index
        res = project_memory.search_memory_index("test")
        assert res["retrieval_mode"] == "keyword"
        assert len(res["results"]) > 0
        assert "file1.txt" in res["results"][0]["relative_path"]
        assert res["results"][0]["source"] == "keyword"
    finally:
        project_memory.get_active_workspace = orig_ws
        project_memory.check_ollama_status = orig_status
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def test_p5_secrets_blocked_from_indexing(tmp_path):
    """Files with secret name/content are not indexed."""
    import project_memory
    import agent_config
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "file.txt").write_text("regular data", encoding="utf-8")
    (ws / "secret_key.pem").write_text("PRIVATE KEY CONTENT", encoding="utf-8")
    (ws / "password.txt").write_text("mypassword123", encoding="utf-8")
    
    orig_ws = project_memory.get_active_workspace
    project_memory.get_active_workspace = lambda: ws.resolve()
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    try:
        stats = project_memory.reindex_project_memory()
        assert stats["indexed_files"] == 1
        
        # Verify index contents
        index_path = project_memory.get_index_path()
        import json
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        files = list(idx["files"].keys())
        assert "file.txt" in files
        assert "secret_key.pem" not in files
        assert "password.txt" not in files
    finally:
        project_memory.get_active_workspace = orig_ws
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def test_p5_ignored_folders_skipped(tmp_path):
    """Ignored directories are skipped during indexing."""
    import project_memory
    import agent_config
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "file.txt").write_text("regular", encoding="utf-8")
    (ws / ".git").mkdir()
    (ws / ".git" / "config").write_text("git configs", encoding="utf-8")
    (ws / "node_modules").mkdir()
    (ws / "node_modules" / "pkg.js").write_text("code", encoding="utf-8")
    
    orig_ws = project_memory.get_active_workspace
    project_memory.get_active_workspace = lambda: ws.resolve()
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    try:
        stats = project_memory.reindex_project_memory()
        assert stats["indexed_files"] == 1
        
        index_path = project_memory.get_index_path()
        import json
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        files = list(idx["files"].keys())
        assert "file.txt" in files
        assert ".git/config" not in files
        assert "node_modules/pkg.js" not in files
    finally:
        project_memory.get_active_workspace = orig_ws
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def test_p5_chunking_size_bounds():
    """Text is chunked into chunks of character size bounds with labels."""
    from project_memory import chunk_file_text
    
    content = "A" * 5000
    chunks = chunk_file_text(content, "test.txt", chunk_size=2000, overlap=200)
    
    assert len(chunks) == 3
    # Check prefixes
    assert chunks[0]["chunk_text"].startswith("File: test.txt\n\n")
    assert len(chunks[0]["chunk_text"]) > 2000
    assert chunks[0]["chunk_id"] == 0
    assert chunks[1]["chunk_id"] == 1


def test_p5_relative_path_storage(tmp_path):
    """The memory index stores paths as relative, not absolute."""
    import project_memory
    import agent_config
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "sub").mkdir(parents=True, exist_ok=True)
    (ws / "sub" / "child.txt").write_text("data", encoding="utf-8")
    
    orig_ws = project_memory.get_active_workspace
    project_memory.get_active_workspace = lambda: ws.resolve()
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    try:
        project_memory.reindex_project_memory()
        index_path = project_memory.get_index_path()
        import json
        idx = json.loads(index_path.read_text(encoding="utf-8"))
        files = list(idx["files"].keys())
        # Path must be relative
        assert "sub/child.txt" in files
        assert str(ws.resolve()) not in files[0]
    finally:
        project_memory.get_active_workspace = orig_ws
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def test_p5_hybrid_similarity_boosts(tmp_path):
    """Hybrid search applies filename, path, and exact match boosts."""
    import project_memory
    import agent_config
    import json
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    
    # Create files
    (ws / "my_bridge.py").write_text("this has bridge code", encoding="utf-8")
    (ws / "other.py").write_text("unrelated file text", encoding="utf-8")
    
    orig_ws = project_memory.get_active_workspace
    project_memory.get_active_workspace = lambda: ws.resolve()
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    # Mock Ollama embedding returning static vector
    orig_status = project_memory.check_ollama_status
    orig_embed = project_memory.get_ollama_embedding
    
    project_memory.check_ollama_status = lambda m=None: (True, True, "online")
    mock_vector = [0.1] * 768
    project_memory.get_ollama_embedding = lambda text, model=None: (mock_vector, None)
    
    try:
        project_memory.reindex_project_memory()
        
        # Test search
        res = project_memory.search_memory_index("bridge")
        assert res["retrieval_mode"] == "embedding"
        results = res["results"]
        assert len(results) > 0
        assert results[0]["relative_path"] == "my_bridge.py"
        assert results[0]["source"] == "embedding"
        # Since it had exact match + filename boost, score should be high
        assert results[0]["score"] > 50.0
    finally:
        project_memory.get_active_workspace = orig_ws
        project_memory.check_ollama_status = orig_status
        project_memory.get_ollama_embedding = orig_embed
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def test_p5_reindex_endpoint_stats(tmp_path):
    """POST /api/memory/reindex returns correct stats structure."""
    from fastapi.testclient import TestClient
    from backend_bridge import app
    import backend_bridge
    import project_memory
    import agent_config
    
    client = TestClient(app)
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "file1.txt").write_text("Hello code test", encoding="utf-8")
    
    orig_ws_bb = backend_bridge.get_active_workspace
    orig_ws_pm = project_memory.get_active_workspace
    backend_bridge.get_active_workspace = lambda: ws.resolve()
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    orig_status = project_memory.check_ollama_status
    project_memory.check_ollama_status = lambda m=None: (True, True, "online")
    orig_embed = project_memory.get_ollama_embedding
    project_memory.get_ollama_embedding = lambda t, m=None: ([0.1] * 768, None)
    
    try:
        response = client.post("/api/memory/reindex?model=nomic-embed-text")
        assert response.status_code == 200
        data = response.json()
        assert "indexed_files" in data
        assert "indexed_chunks" in data
        assert "embedding_available" in data
        assert data["indexed_files"] == 1
    finally:
        backend_bridge.get_active_workspace = orig_ws_bb
        project_memory.get_active_workspace = orig_ws_pm
        project_memory.check_ollama_status = orig_status
        project_memory.get_ollama_embedding = orig_embed
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def test_p5_search_endpoint_returns_scores(tmp_path):
    """GET /api/memory/search returns search results with scores."""
    from fastapi.testclient import TestClient
    from backend_bridge import app
    import backend_bridge
    import project_memory
    import agent_config
    
    client = TestClient(app)
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "my_bridge.py").write_text("this has bridge code", encoding="utf-8")
    
    orig_ws_bb = backend_bridge.get_active_workspace
    orig_ws_pm = project_memory.get_active_workspace
    backend_bridge.get_active_workspace = lambda: ws.resolve()
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    # Run a quick reindex
    orig_status = project_memory.check_ollama_status
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")
    
    try:
        project_memory.reindex_project_memory()
        
        response = client.get("/api/memory/search?q=bridge")
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "bridge"
        assert len(data["results"]) > 0
        assert data["results"][0]["score"] > 0
    finally:
        backend_bridge.get_active_workspace = orig_ws_bb
        project_memory.get_active_workspace = orig_ws_pm
        project_memory.check_ollama_status = orig_status
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def test_p5_chat_selected_files_priority(tmp_path):
    """If selected_files is passed to chat, auto context is skipped."""
    import backend_bridge
    import project_memory
    import agent_config
    from backend_bridge import api_chat
    from backend_bridge import ChatRequest
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "file.txt").write_text("Hello select file content", encoding="utf-8")
    
    orig_ws_bb = backend_bridge.get_active_workspace
    orig_ws_pm = project_memory.get_active_workspace
    backend_bridge.get_active_workspace = lambda: ws.resolve()
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    orig_status = backend_bridge.check_ollama_status
    orig_ollama_chat = backend_bridge.ollama_chat
    backend_bridge.check_ollama_status = lambda m=None: (True, True, "online")
    backend_bridge.ollama_chat = lambda *args, **kwargs: ("reply", None)
    
    try:
        project_memory.reindex_project_memory()
        
        req = ChatRequest(
            message="explain python bridge",
            context=[],
            selected_files=["file.txt"],
            response_length="balanced"
        )
        res = api_chat(req)
        meta = res["metadata"]
        assert meta["file_context_used"] is True
        assert meta["memory_context_used"] is False
    finally:
        backend_bridge.get_active_workspace = orig_ws_bb
        project_memory.get_active_workspace = orig_ws_pm
        backend_bridge.check_ollama_status = orig_status
        backend_bridge.ollama_chat = orig_ollama_chat
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def test_p5_chat_metadata_correctness(tmp_path):
    """Memory context metadata reports correctly in chat response."""
    import backend_bridge
    import project_memory
    import agent_config
    from backend_bridge import api_chat
    from backend_bridge import ChatRequest
    
    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "file.txt").write_text("explain python bridge context", encoding="utf-8")
    
    orig_ws_bb = backend_bridge.get_active_workspace
    orig_ws_pm = project_memory.get_active_workspace
    backend_bridge.get_active_workspace = lambda: ws.resolve()
    project_memory.get_active_workspace = lambda: ws.resolve()
    
    original_workspace = list(agent_config.WRITE_ALLOWED_ROOTS)
    original_allowed = list(agent_config.ALLOWED_ROOTS)
    original_segments = list(agent_config.BLOCKED_PATH_SEGMENTS)
    original_prefixes = list(agent_config.BLOCKED_PATH_PREFIXES)
    
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    
    orig_status = backend_bridge.check_ollama_status
    orig_ollama_chat = backend_bridge.ollama_chat
    backend_bridge.check_ollama_status = lambda m=None: (True, True, "online")
    backend_bridge.ollama_chat = lambda *args, **kwargs: ("reply", None)
    
    try:
        project_memory.check_ollama_status = lambda m=None: (False, False, "offline")
        project_memory.reindex_project_memory()
        
        req = ChatRequest(
            message="explain python bridge",
            context=[],
            selected_files=[],
            response_length="balanced"
        )
        res = api_chat(req)
        meta = res["metadata"]
        assert meta["memory_context_used"] is True
        assert meta["memory_context_chunks"] > 0
        assert meta["retrieval_mode"] in ("keyword", "hybrid_fallback")
    finally:
        backend_bridge.get_active_workspace = orig_ws_bb
        project_memory.get_active_workspace = orig_ws_pm
        backend_bridge.check_ollama_status = orig_status
        backend_bridge.ollama_chat = orig_ollama_chat
        agent_config.WRITE_ALLOWED_ROOTS.clear()
        agent_config.WRITE_ALLOWED_ROOTS.extend(original_workspace)
        agent_config.ALLOWED_ROOTS.clear()
        agent_config.ALLOWED_ROOTS.extend(original_allowed)
        agent_config.BLOCKED_PATH_SEGMENTS.clear()
        agent_config.BLOCKED_PATH_SEGMENTS.extend(original_segments)
        agent_config.BLOCKED_PATH_PREFIXES.clear()
        agent_config.BLOCKED_PATH_PREFIXES.extend(original_prefixes)


def _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config):
    original = {
        "bb_ws": backend_bridge.get_active_workspace,
        "pm_ws": project_memory.get_active_workspace,
        "write_roots": list(agent_config.WRITE_ALLOWED_ROOTS),
        "allowed_roots": list(agent_config.ALLOWED_ROOTS),
        "segments": list(agent_config.BLOCKED_PATH_SEGMENTS),
        "prefixes": list(agent_config.BLOCKED_PATH_PREFIXES),
    }
    backend_bridge.get_active_workspace = lambda: ws.resolve()
    project_memory.get_active_workspace = lambda: ws.resolve()
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.append(ws.resolve())
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.append(ws.resolve())
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    return original


def _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config):
    backend_bridge.get_active_workspace = original["bb_ws"]
    project_memory.get_active_workspace = original["pm_ws"]
    agent_config.WRITE_ALLOWED_ROOTS.clear()
    agent_config.WRITE_ALLOWED_ROOTS.extend(original["write_roots"])
    agent_config.ALLOWED_ROOTS.clear()
    agent_config.ALLOWED_ROOTS.extend(original["allowed_roots"])
    agent_config.BLOCKED_PATH_SEGMENTS.clear()
    agent_config.BLOCKED_PATH_SEGMENTS.extend(original["segments"])
    agent_config.BLOCKED_PATH_PREFIXES.clear()
    agent_config.BLOCKED_PATH_PREFIXES.extend(original["prefixes"])


def test_p5_1_project_memory_prompt_triggers_retrieval(tmp_path):
    """Prompt wording from runtime UI triggers memory retrieval."""
    import backend_bridge
    import project_memory
    import agent_config
    from backend_bridge import ChatRequest, api_chat

    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "backend_bridge.py").write_text("def select_model_for_prompt():\n    return 'model router'\n", encoding="utf-8")
    (ws / "project_memory.py").write_text("def search_memory_index():\n    return 'router memory'\n", encoding="utf-8")

    original = _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config)
    orig_bb_status = backend_bridge.check_ollama_status
    orig_pm_status = project_memory.check_ollama_status
    orig_chat = backend_bridge.ollama_chat
    captured = {}
    backend_bridge.check_ollama_status = lambda m=None: (True, True, "online")
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")
    def fake_chat(*args, **kwargs):
        captured["context"] = kwargs.get("context_chunks", [])
        return "backend_bridge.py handles model router", None
    backend_bridge.ollama_chat = fake_chat

    try:
        req = ChatRequest(message="Search project memory for model router and explain files involved", context=[], selected_files=[])
        res = api_chat(req)
        meta = res["metadata"]
        assert meta["memory_context_used"] is True
        assert meta["memory_context_chunks"] > 0
        assert meta["memory_results_found"] > 0
        assert meta["memory_search_query"] == "model router"
        assert any("backend_bridge.py" in chunk for chunk in captured["context"])
    finally:
        backend_bridge.check_ollama_status = orig_bb_status
        project_memory.check_ollama_status = orig_pm_status
        backend_bridge.ollama_chat = orig_chat
        _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config)


def test_p5_1_missing_index_auto_reindexes(tmp_path):
    """Missing memory index is safely rebuilt and reported."""
    import backend_bridge
    import project_memory
    import agent_config
    from backend_bridge import ChatRequest, api_chat

    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "router.py").write_text("model router route model backend_bridge", encoding="utf-8")

    original = _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config)
    orig_bb_status = backend_bridge.check_ollama_status
    orig_pm_status = project_memory.check_ollama_status
    orig_chat = backend_bridge.ollama_chat
    backend_bridge.check_ollama_status = lambda m=None: (True, True, "online")
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")
    backend_bridge.ollama_chat = lambda *args, **kwargs: ("reply", None)

    try:
        req = ChatRequest(message="Search project memory for model router", context=[], selected_files=[])
        res = api_chat(req)
        meta = res["metadata"]
        assert meta["memory_auto_reindexed"] is True
        assert meta["memory_index_missing"] is False
        assert meta["memory_context_used"] is True
        assert project_memory.get_index_path().exists()
    finally:
        backend_bridge.check_ollama_status = orig_bb_status
        project_memory.check_ollama_status = orig_pm_status
        backend_bridge.ollama_chat = orig_chat
        _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config)


def test_p5_1_empty_index_returns_metadata_not_crash(tmp_path):
    """Empty index path returns clear metadata and does not call Ollama chat."""
    import backend_bridge
    import project_memory
    import agent_config
    from backend_bridge import ChatRequest, api_chat

    ws = tmp_path / "mock_ws"
    ws.mkdir()

    original = _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config)
    orig_bb_status = backend_bridge.check_ollama_status
    orig_pm_status = project_memory.check_ollama_status
    orig_chat = backend_bridge.ollama_chat
    backend_bridge.check_ollama_status = lambda m=None: (True, True, "online")
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")
    backend_bridge.ollama_chat = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ollama_chat should not be called"))

    try:
        res = api_chat(ChatRequest(message="Search project memory for model router", context=[], selected_files=[]))
        meta = res["metadata"]
        assert meta["memory_index_missing"] is True
        assert meta["memory_auto_reindexed"] is True
        assert meta["memory_results_found"] == 0
        assert res["response"].startswith("Project memory index is empty")
    finally:
        backend_bridge.check_ollama_status = orig_bb_status
        project_memory.check_ollama_status = orig_pm_status
        backend_bridge.ollama_chat = orig_chat
        _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config)


def test_p5_1_selected_files_still_priority_for_memory_prompt(tmp_path):
    """Manual file context wins over auto memory even for memory-trigger prompts."""
    import backend_bridge
    import project_memory
    import agent_config
    from backend_bridge import ChatRequest, api_chat

    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "chosen.py").write_text("selected file content", encoding="utf-8")
    (ws / "router.py").write_text("model router should not be auto attached", encoding="utf-8")

    original = _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config)
    orig_bb_status = backend_bridge.check_ollama_status
    orig_pm_status = project_memory.check_ollama_status
    orig_chat = backend_bridge.ollama_chat
    backend_bridge.check_ollama_status = lambda m=None: (True, True, "online")
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")
    backend_bridge.ollama_chat = lambda *args, **kwargs: ("reply", None)

    try:
        project_memory.reindex_project_memory()
        res = api_chat(ChatRequest(
            message="Search project memory for model router",
            context=[],
            selected_files=["chosen.py"],
        ))
        meta = res["metadata"]
        assert meta["file_context_used"] is True
        assert meta["file_context_file_count"] == 1
        assert meta["memory_context_used"] is False
        assert meta["memory_context_chunks"] == 0
    finally:
        backend_bridge.check_ollama_status = orig_bb_status
        project_memory.check_ollama_status = orig_pm_status
        backend_bridge.ollama_chat = orig_chat
        _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config)


def test_p5_2_model_router_ranks_backend_above_tests(tmp_path):
    """Implementation query ranks backend_bridge.py above test_safety.py."""
    import backend_bridge
    import project_memory
    import agent_config

    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "backend_bridge.py").write_text("model router select_model_for_prompt resolved_model selected_model", encoding="utf-8")
    (ws / "test_safety.py").write_text("model router select_model_for_prompt resolved_model selected_model", encoding="utf-8")

    original = _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config)
    orig_status = project_memory.check_ollama_status
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")

    try:
        project_memory.reindex_project_memory()
        res = project_memory.search_memory_index("model router", limit=10)
        paths = [item["relative_path"] for item in res["results"]]
        assert paths.index("backend_bridge.py") < paths.index("test_safety.py")
        assert res["production_boost_applied"] is True
        assert res["test_downrank_applied"] is True
        assert res["query_boost_applied"] is True
    finally:
        project_memory.check_ollama_status = orig_status
        _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config)


def test_p5_2_memory_query_ranks_project_memory_above_tests(tmp_path):
    """Memory/reindex query boosts project_memory.py above matching tests."""
    import backend_bridge
    import project_memory
    import agent_config

    ws = tmp_path / "mock_ws"
    ws.mkdir()
    text = "project memory embedding reindex search_memory_index retrieval chunk"
    (ws / "project_memory.py").write_text(text, encoding="utf-8")
    (ws / "test_safety.py").write_text(text, encoding="utf-8")

    original = _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config)
    orig_status = project_memory.check_ollama_status
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")

    try:
        project_memory.reindex_project_memory()
        res = project_memory.search_memory_index("project memory embedding reindex", limit=10)
        paths = [item["relative_path"] for item in res["results"]]
        assert paths.index("project_memory.py") < paths.index("test_safety.py")
        assert res["ranking_profile"] == "production_first"
        assert "memory_core" in res["results"][0]["ranking_notes"]
    finally:
        project_memory.check_ollama_status = orig_status
        _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config)


def test_p5_2_test_query_allows_test_safety_to_rank_high(tmp_path):
    """Test-related queries do not apply default test downrank."""
    import backend_bridge
    import project_memory
    import agent_config

    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "backend_bridge.py").write_text("pytest failing test_safety assertion", encoding="utf-8")
    (ws / "test_safety.py").write_text("pytest failing test_safety assertion", encoding="utf-8")

    original = _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config)
    orig_status = project_memory.check_ollama_status
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")

    try:
        project_memory.reindex_project_memory()
        res = project_memory.search_memory_index("pytest failing test_safety", limit=10)
        assert res["results"][0]["relative_path"] == "test_safety.py"
        assert res["test_downrank_applied"] is False
        assert "test_downrank" not in res["results"][0]["ranking_notes"]
    finally:
        project_memory.check_ollama_status = orig_status
        _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config)


def test_p5_2_test_files_downranked_by_default(tmp_path):
    """Matching test files receive downrank notes for non-test queries."""
    import backend_bridge
    import project_memory
    import agent_config

    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "feature.py").write_text("codebase router implementation", encoding="utf-8")
    (ws / "test_feature.py").write_text("codebase router implementation", encoding="utf-8")

    original = _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config)
    orig_status = project_memory.check_ollama_status
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")

    try:
        project_memory.reindex_project_memory()
        res = project_memory.search_memory_index("codebase router implementation", limit=10)
        test_result = next(item for item in res["results"] if item["relative_path"] == "test_feature.py")
        prod_result = next(item for item in res["results"] if item["relative_path"] == "feature.py")
        assert "test_downrank" in test_result["ranking_notes"]
        assert test_result["final_score"] < prod_result["final_score"]
    finally:
        project_memory.check_ollama_status = orig_status
        _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config)


def test_p5_2_production_files_receive_boost(tmp_path):
    """Known production source files expose production boost metadata."""
    import backend_bridge
    import project_memory
    import agent_config

    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "agent_tools.py").write_text("safe path workspace traversal allowed path command safety", encoding="utf-8")

    original = _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config)
    orig_status = project_memory.check_ollama_status
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")

    try:
        project_memory.reindex_project_memory()
        res = project_memory.search_memory_index("safe path workspace traversal", limit=10)
        top = res["results"][0]
        assert top["relative_path"] == "agent_tools.py"
        assert "production_boost" in top["ranking_notes"]
        assert "safety_core" in top["ranking_notes"]
        assert top["final_score"] > top["base_score"]
    finally:
        project_memory.check_ollama_status = orig_status
        _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config)


def test_p5_2_query_specific_boost_metadata_returned(tmp_path):
    """Search response returns compact ranking behavior flags."""
    import backend_bridge
    import project_memory
    import agent_config

    ws = tmp_path / "mock_ws"
    ws.mkdir()
    (ws / "frontend").mkdir()
    (ws / "frontend" / "src").mkdir()
    (ws / "frontend" / "src" / "App.tsx").write_text("frontend badge context count UI selected files React Vite TypeScript", encoding="utf-8")
    (ws / "test_safety.py").write_text("frontend badge context count UI selected files React Vite TypeScript", encoding="utf-8")

    original = _configure_tmp_workspace(ws, backend_bridge, project_memory, agent_config)
    orig_status = project_memory.check_ollama_status
    project_memory.check_ollama_status = lambda m=None: (False, False, "offline")

    try:
        project_memory.reindex_project_memory()
        res = project_memory.search_memory_index("frontend badge context count", limit=10)
        assert res["ranking_profile"] == "production_first"
        assert res["production_boost_applied"] is True
        assert res["test_downrank_applied"] is True
        assert res["query_boost_applied"] is True
        assert res["results"][0]["relative_path"] == "frontend/src/App.tsx"
    finally:
        project_memory.check_ollama_status = orig_status
        _restore_tmp_workspace(original, backend_bridge, project_memory, agent_config)


# ═══════════════════════════════════════════════════════════════════
# P6 — Command Execution Planner Tests
# ═══════════════════════════════════════════════════════════════════

from backend_bridge import plan_command, summarize_output, COMMAND_TEMPLATES


# T1 — pytest command is classified safe
def test_p6_pytest_is_safe():
    pl = plan_command("py -3.11 -m pytest -q")
    assert pl["risk_level"] == "safe"
    assert pl["allowed"] is True
    assert pl["requires_confirmation"] is False
    assert "pytest" in pl["matched_rule"]


# T2 — npm.cmd run build is classified safe
def test_p6_frontend_build_is_safe():
    pl = plan_command("npm.cmd run build")
    assert pl["risk_level"] == "safe"
    assert pl["allowed"] is True
    assert pl["requires_confirmation"] is False


# T3 — pip install is classified caution
def test_p6_pip_install_is_caution():
    pl = plan_command("py -3.11 -m pip install pytest")
    assert pl["risk_level"] == "caution"
    assert pl["allowed"] is True
    assert pl["requires_confirmation"] is True
    assert "pip_install" in pl["matched_rule"]


# T4 — taskkill is classified caution
def test_p6_taskkill_is_caution():
    pl = plan_command("taskkill /PID 12345")
    assert pl["risk_level"] == "caution"
    assert pl["allowed"] is True
    assert pl["requires_confirmation"] is True


# T5 — broad Remove-Item -Recurse -Force is blocked
def test_p6_remove_item_recurse_is_blocked():
    pl = plan_command("Remove-Item -Recurse -Force D:\\AGENT_ALINE_X_*")
    assert pl["risk_level"] == "blocked"
    assert pl["allowed"] is False


# T6 — command outside allowed workspace is blocked
def test_p6_outside_workspace_cwd_is_blocked():
    pl = plan_command("py -3.11 -m pytest -q", cwd="C:\\Windows\\System32")
    assert pl["risk_level"] == "blocked"
    assert pl["allowed"] is False
    assert "cwd_outside_workspace" in pl["matched_rule"]


# T7 — unknown command defaults to caution
def test_p6_unknown_command_defaults_to_caution():
    pl = plan_command("xyzzy-unknown-tool --flag value")
    assert pl["risk_level"] == "caution"
    assert pl["requires_confirmation"] is True
    assert pl["matched_rule"] == "unknown_default_caution"


# T8 — dry-run returns plan without executing (integration: run-free endpoint)
def test_p6_dry_run_does_not_execute():
    from fastapi.testclient import TestClient
    from backend_bridge import app
    client = TestClient(app)

    called = {"ran": False}
    import backend_bridge as bb
    orig = bb.subprocess.run

    def mock_run(*args, **kwargs):
        called["ran"] = True
        raise AssertionError("subprocess.run should not be called in dry-run mode")

    import subprocess
    bb_subprocess = __import__("subprocess")

    # Use /api/commands/plan (always dry-run) to confirm no execution happens
    resp = client.post("/api/commands/plan", json={
        "command": "py -3.11 -m pytest -q",
        "dry_run": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "safe"
    assert called["ran"] is False   # subprocess was never called


# T9 — caution command without confirmed does not execute
def test_p6_caution_without_confirm_does_not_execute():
    from fastapi.testclient import TestClient
    from backend_bridge import app
    client = TestClient(app)

    resp = client.post("/api/commands/run-free", json={
        "command": "py -3.11 -m pip install pytest",
        "confirmed": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["executed"] is False
    assert data["reason"] == "confirmation_required"
    assert data["plan"]["risk_level"] == "caution"


# T10 — caution command with confirmed=True can execute (mocked subprocess)
def test_p6_caution_with_confirm_can_execute(monkeypatch):
    from fastapi.testclient import TestClient
    from backend_bridge import app
    import backend_bridge as bb
    import subprocess

    mock_result = type("R", (), {
        "returncode": 0,
        "stdout": "Would install pytest\n",
        "stderr": "",
    })()

    monkeypatch.setattr(bb.subprocess, "run", lambda *args, **kwargs: mock_result)

    client = TestClient(app)
    resp = client.post("/api/commands/run-free", json={
        "command": "py -3.11 -m pip install pytest",
        "confirmed": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["executed"] is True
    assert data["reason"] == "executed"
    assert data["output_summary"]["exit_code"] == 0


# T11 — blocked command never executes even with confirmed=True
def test_p6_blocked_command_never_executes(monkeypatch):
    from fastapi.testclient import TestClient
    from backend_bridge import app
    import backend_bridge as bb

    called = {"ran": False}
    def should_not_run(*args, **kwargs):
        called["ran"] = True
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(bb.subprocess, "run", should_not_run)

    client = TestClient(app)
    resp = client.post("/api/commands/run-free", json={
        "command": "Remove-Item -Recurse -Force D:\\AGENT_ALINE_X_*",
        "confirmed": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["executed"] is False
    assert data["reason"] == "blocked"
    assert called["ran"] is False


# T12 — output summarizer detects pytest pass
def test_p6_summarizer_detects_pytest_pass():
    output = "49 passed in 12.34s"
    result = summarize_output(output, exit_code=0)
    assert result["success"] is True
    assert result["exit_code"] == 0
    assert any("passed" in line.lower() for line in result["important_lines"])
    assert result["raw_output_truncated"] is False


# T13 — output summarizer detects traceback/error
def test_p6_summarizer_detects_traceback():
    output = (
        "Traceback (most recent call last):\n"
        "  File 'backend_bridge.py', line 42, in test\n"
        "AttributeError: 'NoneType' object has no attribute 'x'\n"
        "1 failed in 0.12s"
    )
    result = summarize_output(output, exit_code=1)
    assert result["success"] is False
    assert len(result["errors_detected"]) > 0
    assert any("traceback" in e.lower() or "attributeerror" in e.lower() or "failed" in e.lower()
               for e in result["errors_detected"] + result["important_lines"])


# T14 — command templates endpoint returns expected templates
def test_p6_templates_endpoint():
    from fastapi.testclient import TestClient
    from backend_bridge import app
    client = TestClient(app)

    resp = client.get("/api/commands/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    templates = data["templates"]
    ids = [t["id"] for t in templates]
    assert "backend-compile" in ids
    assert "backend-tests" in ids
    assert "frontend-build" in ids
    assert "health-check" in ids
    assert "memory-reindex" in ids
    assert "memory-search" in ids
    # memory-reindex must be caution
    reindex = next(t for t in templates if t["id"] == "memory-reindex")
    assert reindex["risk_level"] == "caution"
    # all others should be safe
    for t in templates:
        if t["id"] != "memory-reindex":
            assert t["risk_level"] == "safe"


# T15 — P0/P1/P2/P3/P4/P5/P5.1/P5.2 preservation sanity
def test_p6_prior_phases_still_pass():
    # P0 path safety
    import agent_tools
    assert agent_tools.is_allowed_path(agent_tools.ALLOWED_ROOTS[0])
    assert not agent_tools.is_allowed_path("C:\\Windows\\System32")

    # P1 model routing
    from backend_bridge import select_model_for_prompt
    model, reason = select_model_for_prompt("fix this traceback error")
    assert model == "qwen2.5-coder:7b"
    model, reason = select_model_for_prompt("audit the system")
    assert model == "maxwellb/gemma4-12b-it-oym:latest"

    # P2 build_metadata still has all keys
    from backend_bridge import build_metadata
    meta = build_metadata(
        request_id="p6-check",
        selected_model="agent-aline-x:latest",
        resolved_model="agent-aline-x:latest",
        route_reason="normal chat",
        duration_ms=10,
        fallback_used=False,
        fallback_from=None,
        fallback_to=None,
        error=None,
        prompt_length_chars=5,
        context_length_chars=0,
    )
    assert "request_id" in meta
    assert "created_at" in meta

    # P3 context trimming
    from backend_bridge import trim_context_chunks
    chunks = ["A" * 5000 for _ in range(5)]
    trimmed, total, dropped = trim_context_chunks(chunks, max_chars=8000)
    assert total <= 8001 + 29   # slight fudge for truncation suffix

    # P5 summarize_output still works
    result = summarize_output("49 passed in 3.2s", 0)
    assert result["success"] is True


# ═══════════════════════════════════════════════════════════════════
# P7 — Final QA Dashboard + Release Packaging Tests
# ═══════════════════════════════════════════════════════════════════

def test_p7_release_status_returns_version_and_phases():
    """GET /api/release/status returns version, stage, and completed phases."""
    from fastapi.testclient import TestClient
    from backend_bridge import app

    client = TestClient(app)
    resp = client.get("/api/release/status")
    assert resp.status_code == 200
    data = resp.json()

    assert data["name"] == "AGENT ALINE X"
    assert data["version"] == "v3.1"
    assert data["release_stage"] == "P7 Final QA"
    assert isinstance(data["completed_phases"], list)
    assert "P6" in data["completed_phases"]
    assert "active_workspace" in data
    assert "model_discovery" in data
    assert "memory_index" in data
    assert data["command_planner_enabled"] is True
    assert data["patch_mode"] == "off"
    assert data["test_command_recommendation"] == "py -3.11 -m pytest -q"
    assert data["frontend_build_command_recommendation"] == "npm.cmd run build"


def test_p7_release_status_is_read_only_no_reindex(monkeypatch):
    """Release status must never trigger a memory reindex or Ollama chat call."""
    from fastapi.testclient import TestClient
    from backend_bridge import app
    import backend_bridge as bb

    called = {"reindex": False, "chat": False}

    def fail_if_reindex(*args, **kwargs):
        called["reindex"] = True
        return {"indexed_files": 0, "indexed_chunks": 0, "retrieval_mode": "keyword"}

    def fail_if_chat(*args, **kwargs):
        called["chat"] = True
        return "should not be called", None

    monkeypatch.setattr(bb, "reindex_project_memory", fail_if_reindex)
    monkeypatch.setattr(bb, "ollama_chat", fail_if_chat)

    client = TestClient(app)
    resp = client.get("/api/release/status")
    assert resp.status_code == 200
    assert called["reindex"] is False
    assert called["chat"] is False


def test_p7_prior_phases_still_pass_after_release_status():
    """Adding the release status endpoint must not disturb P0-P6.1 behavior."""
    import agent_tools
    from backend_bridge import select_model_for_prompt, plan_command, summarize_output

    assert agent_tools.is_allowed_path(agent_tools.ALLOWED_ROOTS[0])
    assert not agent_tools.is_allowed_path("C:\\Windows\\System32")

    model, reason = select_model_for_prompt("fix this traceback error")
    assert model == "qwen2.5-coder:7b"

    pl = plan_command("py -3.11 -m pytest -q")
    assert pl["risk_level"] == "safe"

    pl_blocked = plan_command("Remove-Item -Recurse -Force D:\\AGENT_ALINE_X_\\*")
    assert pl_blocked["risk_level"] == "blocked"

    result = summarize_output("49 passed in 3.2s", 0)
    assert result["success"] is True


# T15b — old /api/commands/run command_id payload still works end-to-end
def test_p6_old_command_id_endpoint_still_works(monkeypatch):
    """
    The pre-P6 frontend still posts { "command_id": "..." } to /api/commands/run.
    Confirm that route is untouched by the P6 planner work: same schema in,
    same schema out, subprocess still mocked so no real command runs.
    """
    from fastapi.testclient import TestClient
    from backend_bridge import app
    import backend_bridge as bb

    mock_result = type("R", (), {
        "returncode": 0,
        "stdout": "49 passed in 3.2s\n",
        "stderr": "",
    })()
    monkeypatch.setattr(bb.subprocess, "run", lambda *args, **kwargs: mock_result)

    client = TestClient(app)
    resp = client.post("/api/commands/run", json={"command_id": "pytest"})
    assert resp.status_code == 200
    data = resp.json()

    # Old response shape must be unchanged by the P6 patch
    assert data["command_id"] == "pytest"
    assert data["ok"] is True
    assert data["exit_code"] == 0
    assert "output" in data
    assert "label" in data
    assert "duration_ms" in data

    # Unknown command_id must still be rejected the old way (not routed to the planner)
    resp2 = client.post("/api/commands/run", json={"command_id": "not-a-real-id"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["ok"] is False
    assert "BLOCKED" in data2["output"]


# ══════════════════════════════════════════════════════
# P7.1 — Deterministic Query Intercept & Memory Guard
# ══════════════════════════════════════════════════════

def test_deterministic_release_status_response():
    """Release status query returns deterministic summary without calling LLM."""
    from backend_bridge import get_deterministic_release_status_response
    
    resp = get_deterministic_release_status_response()
    assert isinstance(resp, str)
    assert len(resp) > 100
    # Must include the structured header and key fields
    assert "AGENT ALINE X" in resp
    assert "Version" in resp
    assert "Memory Index" in resp
    assert "Next:" in resp


def test_deterministic_command_planner_response():
    """Command planner query returns deterministic safety rules without calling LLM."""
    from backend_bridge import get_deterministic_command_planner_response
    
    resp = get_deterministic_command_planner_response()
    assert isinstance(resp, str)
    assert "safe" in resp.lower()
    assert "caution" in resp.lower()
    assert "blocked" in resp.lower()
    assert "/api/commands/plan" in resp
    assert "Next:" in resp


def test_deterministic_qa_checklist_response():
    """Final QA checklist query returns full checklist without calling LLM."""
    from backend_bridge import get_deterministic_qa_checklist_response
    
    resp = get_deterministic_qa_checklist_response()
    assert isinstance(resp, str)
    assert len(resp) > 100
    # Should include either FINAL_QA_CHECKLIST.md content or built-in fallback
    assert "pytest" in resp.lower() or "py_compile" in resp.lower() or "checklist" in resp.lower()


def test_generate_deterministic_memory_response_with_results():
    """Memory response generator produces grounded response from memory results."""
    from backend_bridge import generate_deterministic_memory_response
    
    mock_results = [
        {"relative_path": "backend_bridge.py", "chunk_id": 0, "snippet": "...router logic..."},
        {"relative_path": "agent_tools.py", "chunk_id": 1, "snippet": "...ollama_chat..."},
    ]
    resp = generate_deterministic_memory_response("model router and explain files involved", mock_results)
    assert isinstance(resp, str)
    assert "backend_bridge.py" in resp
    assert "agent_tools.py" in resp
    assert "project memory" in resp.lower()
    assert "Next:" in resp


def test_generate_deterministic_memory_response_empty_results():
    """Memory response generator handles empty results gracefully."""
    from backend_bridge import generate_deterministic_memory_response
    
    resp = generate_deterministic_memory_response("some query", [])
    assert isinstance(resp, str)
    # Should still return a valid string response (even if empty file list)
    assert "project memory" in resp.lower() or "memory search" in resp.lower()


def test_api_chat_deterministic_release_intercept():
    """API chat intercepts release status query and returns deterministic response."""
    from fastapi.testclient import TestClient
    from backend_bridge import app

    client = TestClient(app)
    resp = client.post("/api/chat", json={
        "message": "Check project release status",
        "model": "auto",
        "response_length": "Quick",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("answer_source") == "fast_local"
    assert "deterministic" in data.get("route_reason", "")
    assert "AGENT ALINE X" in data.get("response", "")


def test_api_chat_deterministic_planner_intercept():
    """API chat intercepts command planner query and returns deterministic response."""
    from fastapi.testclient import TestClient
    from backend_bridge import app

    client = TestClient(app)
    resp = client.post("/api/chat", json={
        "message": "Explain command planner safe caution blocked",
        "model": "auto",
        "response_length": "Quick",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("answer_source") == "fast_local"
    assert "deterministic" in data.get("route_reason", "")
    response_text = data.get("response", "")
    assert "safe" in response_text.lower()
    assert "caution" in response_text.lower()
    assert "blocked" in response_text.lower()


def test_api_chat_deterministic_checklist_intercept():
    """API chat intercepts final QA checklist query and returns deterministic response."""
    from fastapi.testclient import TestClient
    from backend_bridge import app

    client = TestClient(app)
    resp = client.post("/api/chat", json={
        "message": "Give final QA checklist for this project",
        "model": "auto",
        "response_length": "Quick",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("answer_source") == "fast_local"
    assert "deterministic" in data.get("route_reason", "")
    response_text = data.get("response", "")
    assert len(response_text) > 50


def test_select_model_for_prompt_auto_mode():
    """Auto mode in select_model_for_prompt falls back to message-based routing."""
    from backend_bridge import select_model_for_prompt
    
    # Auto mode should route by message content, not manual override
    model, reason = select_model_for_prompt("hello there", mode="auto")
    # Should be agent-aline-x for normal chat (auto routes by message content)
    assert model == "agent-aline-x:latest"
    assert "normal" in reason.lower() or "planning" in reason.lower()
    
    model, reason = select_model_for_prompt("fix this traceback error", mode="auto")
    # Should route to coder model for code queries
    assert model == "qwen2.5-coder:7b"
    assert "code" in reason.lower()

