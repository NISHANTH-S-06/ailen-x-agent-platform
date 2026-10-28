"""
agent_ui.py — AGENT ALINE X  |  Professional Streamlit UI  v1.3
Run with:  streamlit run agent_ui.py

v1.1 Changes:
- Fixed XSS: chat messages now HTML-escaped before rendering
- Added secret/credential file blocking in file explorer
- Added command duration display
- Added duplicate command context deduplication
- Added empty context warning before agent ask
- Added context size warning when too large
- Added "blocked" indicator in file listing for secret files
- Improved quick prompts
- Enforces MAX_CONTEXT_CHUNKS limit

v1.2 Changes (NEW):
- Git Diff Viewer: colored diff output with context add
- File Range Reader: read specific line ranges from files
- Test Failure Analyzer: parse pytest failures, show table + agent fix
- Export Audit Report: in-memory .txt download of full session
- Full Safe Audit: run ALL safe commands + comprehensive agent summary

v1.3 Changes (NEW):
- Multi-model support: agent-aline-x + maxwellb/gemma4-12b-it-oym
- Model selector in sidebar with friendly labels
- Greeting / small-talk fallback (no Ollama call needed)
- Temperature slider + num_predict selector in sidebar
- Test Active Model button with latency display
- Active model badge shown in header
"""

import html
import time
import streamlit as st

from agent_config import (
    ALLOWED_ROOTS,
    SAFE_COMMANDS,
    MODEL_NAME,
    DEFAULT_MODEL,
    AVAILABLE_MODELS,
    MODEL_LABELS,
    MAX_FILE_READ_LINES,
    MAX_CONTEXT_CHUNKS,
    MAX_CONTEXT_CHARS_WARN,
)
from agent_tools import (
    check_ollama_status,
    list_directory,
    read_file,
    read_file_range,
    run_safe_command,
    make_context_chunk_from_file,
    make_context_chunk_from_command,
    ollama_chat,
    safe_resolve,
)

# ─────────────────────────────────────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AGENT ALINE X",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS — Dark Professional Theme
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  :root {
    --bg-primary:    #0d0f14;
    --bg-card:       #13161e;
    --bg-card2:      #1a1e2a;
    --accent-blue:   #4f8ef7;
    --accent-green:  #22c55e;
    --accent-amber:  #f59e0b;
    --accent-red:    #ef4444;
    --accent-purple: #a78bfa;
    --text-primary:  #e2e8f0;
    --text-muted:    #64748b;
    --border:        #1e2330;
  }

  html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg-primary) !important;
    font-family: 'Inter', sans-serif !important;
    color: var(--text-primary) !important;
  }
  [data-testid="stHeader"] { background: transparent !important; }

  .hero-header {
    background: linear-gradient(135deg, #0d1117 0%, #131a2e 40%, #0d1117 100%);
    border: 1px solid #1e2d4a;
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
  }
  .hero-header::before {
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(ellipse at 30% 50%, rgba(79,142,247,0.06) 0%, transparent 60%);
    pointer-events: none;
  }
  .hero-title {
    font-size: 2.4rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    background: linear-gradient(90deg, #4f8ef7, #a78bfa, #4f8ef7);
    background-size: 200%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 4px 0;
  }
  .hero-sub {
    font-size: 0.95rem;
    color: var(--text-muted);
    margin: 0;
    letter-spacing: 0.03em;
  }

  .badge-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
  .badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 14px;
    border-radius: 99px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    border: 1px solid;
  }
  .badge-green  { background: rgba(34,197,94,0.12);  color: #22c55e; border-color: rgba(34,197,94,0.3); }
  .badge-blue   { background: rgba(79,142,247,0.12); color: #4f8ef7; border-color: rgba(79,142,247,0.3); }
  .badge-amber  { background: rgba(245,158,11,0.12); color: #f59e0b; border-color: rgba(245,158,11,0.3); }
  .badge-red    { background: rgba(239,68,68,0.12);  color: #ef4444; border-color: rgba(239,68,68,0.3); }
  .badge-purple { background: rgba(167,139,250,0.12);color: #a78bfa; border-color: rgba(167,139,250,0.3); }

  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
  }
  .card-title {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: 12px;
  }

  /* Chat bubbles — safe: content is always HTML-escaped before insertion */
  .chat-user {
    background: linear-gradient(135deg, #1e2d4a, #1a2240);
    border: 1px solid #2a3d5a;
    border-radius: 12px 12px 4px 12px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #cbd5e1;
    font-size: 0.9rem;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .chat-agent {
    background: linear-gradient(135deg, #131a1f, #111820);
    border: 1px solid #1e2d3a;
    border-left: 3px solid #4f8ef7;
    border-radius: 4px 12px 12px 12px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #e2e8f0;
    font-size: 0.9rem;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .chat-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
    color: var(--text-muted);
  }
  .chat-label-agent { color: #4f8ef7; }

  .cmd-card {
    background: #0d1117;
    border: 1px solid #1e2330;
    border-left: 3px solid #22c55e;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 10px 0;
  }
  .cmd-card-error { border-left-color: #ef4444; }
  .cmd-meta {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-family: 'JetBrains Mono', monospace;
    margin-bottom: 8px;
  }

  .ctx-chunk {
    background: #0d1117;
    border: 1px solid #1e2330;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 0.82rem;
    font-family: 'JetBrains Mono', monospace;
    color: #94a3b8;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 150px;
    overflow-y: auto;
  }

  [data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: var(--bg-card) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid var(--border) !important;
  }
  [data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-muted) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    padding: 8px 18px !important;
  }
  [data-testid="stTabs"] [aria-selected="true"] {
    background: linear-gradient(135deg, #1e2d4a, #1a2240) !important;
    color: #4f8ef7 !important;
  }

  [data-testid="stButton"] > button {
    background: linear-gradient(135deg, #1e2d4a, #1a2240) !important;
    color: #4f8ef7 !important;
    border: 1px solid rgba(79,142,247,0.3) !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    transition: all 0.2s ease !important;
  }
  [data-testid="stButton"] > button:hover {
    background: linear-gradient(135deg, #2a3d5a, #1e2d4a) !important;
    border-color: #4f8ef7 !important;
    box-shadow: 0 0 16px rgba(79,142,247,0.2) !important;
    transform: translateY(-1px) !important;
  }
  [data-testid="stButton"] > button:active { transform: translateY(0) !important; }

  [data-testid="stTextInput"] input,
  [data-testid="stTextArea"] textarea {
    background: #0d1117 !important;
    border: 1px solid #1e2330 !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
  }
  [data-testid="stTextInput"] input:focus,
  [data-testid="stTextArea"] textarea:focus {
    border-color: #4f8ef7 !important;
    box-shadow: 0 0 0 2px rgba(79,142,247,0.2) !important;
  }

  [data-testid="stNumberInput"] input {
    background: #0d1117 !important;
    border: 1px solid #1e2330 !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
  }

  [data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
  }
  [data-testid="stExpander"] summary {
    color: var(--text-primary) !important;
    font-weight: 500 !important;
  }

  [data-testid="stAlert"] { border-radius: 10px !important; }
  hr { border-color: var(--border) !important; margin: 20px 0 !important; }

  [data-testid="stSelectbox"] > div > div {
    background: #0d1117 !important;
    border: 1px solid #1e2330 !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
  }

  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg-primary); }
  ::-webkit-scrollbar-thumb { background: #2a3040; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #3a4050; }

  .safety-item {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.875rem;
  }
  .safety-item:last-child { border-bottom: none; }
  .safety-icon { font-size: 1rem; min-width: 22px; }

  .workflow-step {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 16px;
    background: #0d1117;
    border: 1px solid #1e2330;
    border-radius: 8px;
    margin: 6px 0;
    font-size: 0.85rem;
  }
  .step-num {
    width: 26px; height: 26px;
    background: linear-gradient(135deg, #1e2d4a, #1a2240);
    border: 1px solid rgba(79,142,247,0.4);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    color: #4f8ef7;
    flex-shrink: 0;
  }

  .file-row {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 0.85rem;
    transition: background 0.15s;
  }
  .file-row:hover { background: rgba(79,142,247,0.05); }
  .file-name { flex: 1; font-family: 'JetBrains Mono', monospace; color: #cbd5e1; }
  .file-name-blocked { color: #ef4444; }
  .file-type { color: var(--text-muted); min-width: 40px; font-size: 0.75rem; }
  .file-size { color: var(--text-muted); min-width: 80px; text-align: right; font-size: 0.78rem; }

  #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Session State Initialisation
# ─────────────────────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "context_chunks":    [],      # list of {"source": str, "content": str}
        "chat_history":      [],      # list of {"role": "user"|"agent", "text": str}
        "last_cmd_results":  {},      # key → result dict
        "cmd_context_keys":  set(),   # tracks which cmd keys are already in context
        "ollama_ok":         None,
        "model_ok":          None,
        "ollama_msg":        "",
        "status_checked_at": 0.0,
        "selected_model":    DEFAULT_MODEL,
        "llm_temp":          0.1,
        "llm_num_predict":   800,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ─────────────────────────────────────────────────────────────────────────────
# Helper Utilities
# ─────────────────────────────────────────────────────────────────────────────

def refresh_status(force: bool = False):
    now = time.time()
    if force or st.session_state.ollama_ok is None or (now - st.session_state.status_checked_at > 30):
        selected_model = st.session_state.get("selected_model", DEFAULT_MODEL)
        ok, model_ok, msg = check_ollama_status(selected_model)
        st.session_state.ollama_ok  = ok
        st.session_state.model_ok   = model_ok
        st.session_state.ollama_msg = msg
        st.session_state.status_checked_at = now


def add_context(source: str, content: str):
    """Add a context chunk, enforcing MAX_CONTEXT_CHUNKS by dropping oldest."""
    st.session_state.context_chunks.append({"source": source, "content": content})
    # Enforce limit
    while len(st.session_state.context_chunks) > MAX_CONTEXT_CHUNKS:
        st.session_state.context_chunks.pop(0)


def context_size_chars() -> int:
    return sum(len(c["content"]) for c in st.session_state.context_chunks)


def fmt_size(n) -> str:
    if n is None:
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n/1024:.1f} KB"
    return f"{n/1024/1024:.1f} MB"


def run_cmd_and_add(key: str) -> dict:
    """
    Run a safe command, store result, add to context (deduplicated), return result dict.
    Replaces any existing context chunk for this command key.
    """
    result = run_safe_command(key)
    st.session_state.last_cmd_results[key] = result
    chunk_content = make_context_chunk_from_command(result)
    source_key = f"cmd:{key}"

    # Remove existing chunk for this command to avoid duplicate context
    st.session_state.context_chunks = [
        c for c in st.session_state.context_chunks
        if c["source"] != source_key
    ]
    if source_key in st.session_state.cmd_context_keys:
        st.session_state.cmd_context_keys.discard(source_key)

    add_context(source_key, chunk_content)
    st.session_state.cmd_context_keys.add(source_key)
    return result



# Greeting / small-talk keywords — never require Ollama
_GREETINGS = {
    "hi", "hello", "hey", "vanakkam", "ready", "ready ah", "readyah",
    "test", "are you there", "you there", "hai", "helo", "heya",
    "wassup", "sup", "yo", "namaste", "hola", "good morning",
    "good evening", "good afternoon", "start", "begin", "ping",
}

def _is_greeting(text: str) -> bool:
    """Return True if the message is a simple greeting / small-talk."""
    cleaned = text.strip().lower()
    for ch in "?!.,&":
        cleaned = cleaned.replace(ch, "")
    cleaned = cleaned.strip()
    if cleaned in _GREETINGS:
        return True
    # Short messages (≤ 4 words) containing any greeting word
    words = cleaned.split()
    if len(words) <= 4 and any(w in _GREETINGS for w in words):
        return True
    return False


def ask_agent(question: str) -> str:
    """Ask Ollama with current context; return response string.

    Greetings get an instant local reply — no Ollama call required.
    Project-status questions with empty context get a polite 'Not Checked'.
    All other questions go to Ollama with the active model + LLM settings.
    """
    if _is_greeting(question):
        active_label = MODEL_LABELS.get(
            st.session_state.get("selected_model", DEFAULT_MODEL),
            st.session_state.get("selected_model", DEFAULT_MODEL),
        )
        return (
            f"Hi Nishanth! 👋 AGENT ALINE X is ready.\n\n"
            f"Active model: **{active_label}**\n\n"
            "For project status, run **Quick Audit** (Project Audit tab) or load context "
            "from **Safe Commands** / **File Explorer** first.\n"
            "I'll answer project questions once I have command output to ground my answer on."
        )

    chunks = [c["content"] for c in st.session_state.context_chunks]

    # Project keywords with no context → polite Not Checked (no Ollama call)
    if not chunks:
        _PROJECT_KW = {
            "status", "audit", "risk", "compile", "git", "test",
            "project", "error", "fail", "warning", "build", "deploy",
        }
        if any(kw in question.strip().lower() for kw in _PROJECT_KW):
            return (
                "Not Checked — no command output or file context is loaded yet.\n\n"
                "Run **Quick Audit** (Project Audit tab) or use **Safe Commands** "
                "to load evidence, then ask again."
            )

    response, err = ollama_chat(
        question,
        chunks,
        model=st.session_state.get("selected_model"),
        temperature=st.session_state.get("llm_temp"),
        num_predict=st.session_state.get("llm_num_predict"),
    )
    if err:
        return f"⚠️ {err}"
    return response


def safe_html(text: str) -> str:
    """HTML-escape a string to prevent XSS in rendered HTML blocks."""
    return html.escape(text)


def show_cmd_result(result: dict):
    """Render a command result block safely."""
    ok = result["exit_code"] == 0 and not result["error"]
    border_color = "#22c55e" if ok else "#ef4444"
    icon = "✅" if ok else "❌"
    duration_str = f"{result['duration_ms']}ms" if result.get("duration_ms") else "—"

    # Safe: label and cwd are from our own config, not user input — but escape anyway
    label_safe = safe_html(result["label"])
    cwd_safe   = safe_html(result["cwd"])

    st.markdown(f"""
    <div style="background:#0d1117; border:1px solid #1e2330;
                border-left:3px solid {border_color}; border-radius:8px;
                padding:14px 18px; margin:10px 0;">
      <div class="cmd-meta">
        {icon} <strong>{label_safe}</strong> &nbsp;|&nbsp;
        Exit: <code>{result['exit_code']}</code> &nbsp;|&nbsp;
        Duration: <code>{duration_str}</code> &nbsp;|&nbsp;
        CWD: <code>{cwd_safe}</code>
      </div>
    </div>
    """, unsafe_allow_html=True)
    with st.expander(f"📄 Output — {result['label']}", expanded=True):
        st.code(result["output"], language="text")
        if result.get("truncated"):
            st.warning("⚠️ Output was truncated. Full output added to context.")


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar Controls
# ─────────────────────────────────────────────────────────────────────────────

def on_model_change():
    refresh_status(force=True)

with st.sidebar:
    st.markdown("### ⚙️ Active Model Settings")
    
    st.selectbox(
        "Active Model",
        options=AVAILABLE_MODELS,
        format_func=lambda x: MODEL_LABELS.get(x, x),
        key="selected_model",
        on_change=on_model_change
    )
    
    st.markdown("---")
    st.markdown("### 📊 Performance Controls")
    
    st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.1,
        step=0.05,
        key="llm_temp"
    )
    
    num_predict_options = {
        400: "400 (Quick)",
        800: "800 (Balanced)",
        1200: "1200 (Detailed)"
    }
    st.selectbox(
        "Max Tokens (num_predict)",
        options=[400, 800, 1200],
        format_func=lambda x: num_predict_options[x],
        key="llm_num_predict"
    )
    
    st.markdown("---")
    st.markdown("### 🧪 Test Active Model")
    add_test_to_context = st.checkbox("Add response to context chunks", value=False, key="chk_add_test_ctx")
    
    if st.button("Test Active Model", key="btn_test_model", use_container_width=True):
        with st.spinner("Testing model response..."):
            t_start = time.monotonic()
            resp, err = ollama_chat(
                "Hi, reply in one short line.",
                context_chunks=[],
                model=st.session_state.selected_model,
                temperature=st.session_state.llm_temp,
                num_predict=st.session_state.llm_num_predict
            )
            duration_ms = int((time.monotonic() - t_start) * 1000)
            
            if err:
                st.error(f"Test failed:\n{err}")
            else:
                st.success(f"Latency: {duration_ms}ms")
                st.info(f"Response: {resp}")
                if add_test_to_context:
                    chunk_content = f"TEST RESPONSE (Model: {st.session_state.selected_model}):\n{resp}"
                    add_context("test_active_model", chunk_content)
                    st.success("Added to context chunks!")


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

selected_model = st.session_state.get("selected_model", DEFAULT_MODEL)
refresh_status()

ollama_badge = "badge-green" if st.session_state.ollama_ok  else "badge-red"
model_badge  = "badge-green" if st.session_state.model_ok   else "badge-amber"
ollama_dot   = "🟢"          if st.session_state.ollama_ok  else "🔴"
model_dot    = "🟢"          if st.session_state.model_ok   else "🟡"

st.markdown(f"""
<div class="hero-header">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;">
    <div>
      <h1 class="hero-title">🤖 AGENT ALINE X</h1>
      <p class="hero-sub">Local Safe Project Agent &nbsp;·&nbsp; v1.3 &nbsp;·&nbsp; Read-Only + Safe Commands Mode</p>
    </div>
    <div class="badge-row">
      <span class="badge {ollama_badge}">{ollama_dot} Ollama {'Online' if st.session_state.ollama_ok else 'Offline'}</span>
      <span class="badge {model_badge}">{model_dot} {safe_html(selected_model.split('/')[-1])}</span>
      <span class="badge badge-green">🟢 OCR Project Path</span>
      <span class="badge badge-purple">🛡️ Safety ON · Patch Mode OFF</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.ollama_ok:
    st.error(
        "⚠️ **Ollama is not running.** "
        "Open a terminal and run `ollama serve`, then click **Refresh Status** below.",
        icon="🚨",
    )
elif not st.session_state.model_ok:
    st.error(
        f"⚠️ **Selected model is not available in Ollama. Run: `ollama pull {selected_model}`**",
        icon="🚨",
    )

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("🔄 Refresh Status", key="btn_refresh_status"):
        refresh_status(force=True)
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────

(
    tab_chat,
    tab_cmds,
    tab_files,
    tab_context,
    tab_audit,
    tab_safety,
) = st.tabs([
    "💬 Agent Chat",
    "⚙️ Safe Commands",
    "📂 File Explorer",
    "📋 Context",
    "🔎 Project Audit",
    "🛡️ Safety Panel",
])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — AGENT CHAT
# ═════════════════════════════════════════════════════════════════════════════

with tab_chat:
    st.markdown('<div class="card-title">💬 Chat with AGENT ALINE X</div>', unsafe_allow_html=True)

    # Chat history
    if not st.session_state.chat_history:
        st.markdown("""
        <div style="text-align:center; padding:40px 0; color:#2a3040;">
          <div style="font-size:3rem;">🤖</div>
          <div style="font-size:1rem; margin-top:8px; color:#4a5568;">
            Agent ready. Load context from Safe Commands or File Explorer, then ask a question.
          </div>
          <div style="font-size:0.8rem; margin-top:4px; color:#2a3040;">
            Tip: Run Git Status or Compile first for grounded answers.
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in st.session_state.chat_history:
            # SECURITY: escape ALL user/agent text before inserting into HTML
            text_safe = safe_html(msg["text"])
            if msg["role"] == "user":
                st.markdown(f"""
                <div class="chat-user">
                  <div class="chat-label">👤 YOU</div>
                  {text_safe}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="chat-agent">
                  <div class="chat-label chat-label-agent">🤖 AGENT ALINE X</div>
                  {text_safe}
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Context summary bar
    n_chunks = len(st.session_state.context_chunks)
    ctx_sz   = context_size_chars()
    ctx_color = "#ef4444" if ctx_sz > MAX_CONTEXT_CHARS_WARN else "#4f8ef7"

    st.markdown(
        f'<div style="font-size:0.78rem; color:#64748b; margin-bottom:8px;">'
        f'📋 Context: <strong style="color:{ctx_color}">{n_chunks} chunks</strong>'
        f' · ~{fmt_size(ctx_sz)}'
        f'{"  ⚠️ <span style=\'color:#f59e0b\'>Context large — consider clearing old chunks</span>" if ctx_sz > MAX_CONTEXT_CHARS_WARN else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if n_chunks == 0:
        st.info(
            "📋 **No context loaded.** "
            "Agent will answer with 'Not Checked' for anything needing project evidence. "
            "Go to **⚙️ Safe Commands** or **📂 File Explorer** to load context first.",
            icon="ℹ️",
        )

    # Quick prompts
    quick_prompts = [
        "Based only on current context and command results, what is the project status and one safe next step?",
        "Summarize the git status output. List changed files only. Do not invent anything.",
        "Summarize the compile result. If compile was not run, say Not Checked.",
        "What risks are visible from the loaded context? Give one safe next step.",
    ]
    with st.expander("⚡ Quick Prompts", expanded=False):
        for i, qp in enumerate(quick_prompts):
            if st.button(f"› {qp[:80]}…", key=f"qp_{i}"):
                st.session_state["prefill_chat"] = qp

    # Input
    prefill = st.session_state.pop("prefill_chat", "")
    user_input = st.text_area(
        "Your question",
        value=prefill,
        height=90,
        placeholder="Ask the agent something grounded in the loaded context…",
        key="chat_input",
        label_visibility="collapsed",
    )

    col_ask, col_clear = st.columns([2, 1])
    with col_ask:
        ask_clicked = st.button("🚀 Ask Agent", key="btn_ask", use_container_width=True)
    with col_clear:
        if st.button("🗑️ Clear Chat", key="btn_clear_chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    if ask_clicked:
        q = user_input.strip()
        if not q:
            st.warning("Please enter a question first.")
        elif _is_greeting(q):
            # Greetings get an instant local reply — Ollama not required
            st.session_state.chat_history.append({"role": "user", "text": q})
            st.session_state.chat_history.append({"role": "agent", "text": ask_agent(q)})
            st.rerun()
        elif not st.session_state.ollama_ok:
            st.error("Ollama is not running. Please start it first (`ollama serve`).")
        elif not st.session_state.model_ok:
            st.error(f"Selected model is not available in Ollama. Run: ollama pull {st.session_state.selected_model}")
        else:
            st.session_state.chat_history.append({"role": "user", "text": q})
            with st.spinner("🤖 Agent is thinking…"):
                answer = ask_agent(q)
            st.session_state.chat_history.append({"role": "agent", "text": answer})
            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — SAFE COMMANDS
# ═════════════════════════════════════════════════════════════════════════════

with tab_cmds:
    st.markdown('<div class="card-title">⚙️ Safe Commands — Predefined Only</div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:0.85rem; color:#64748b; margin-bottom:20px;">'
        'Only pre-approved commands run here. No arbitrary input is accepted. '
        'Results are automatically added to agent context (deduplicated — re-running a command replaces previous result).'
        '</p>',
        unsafe_allow_html=True,
    )

    cmd_keys = list(SAFE_COMMANDS.keys())
    cols_per_row = 3
    for row_start in range(0, len(cmd_keys), cols_per_row):
        row_keys = cmd_keys[row_start: row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, key in zip(cols, row_keys):
            spec = SAFE_COMMANDS[key]
            with col:
                btn_label = f"{spec['icon']} {spec['label']}"
                if st.button(btn_label, key=f"cmd_{key}", use_container_width=True):
                    with st.spinner(f"Running {spec['label']}…"):
                        result = run_cmd_and_add(key)
                    st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    has_results = bool(st.session_state.last_cmd_results)
    if has_results:
        st.markdown('<div class="card-title">📄 Command Results This Session</div>', unsafe_allow_html=True)
        for key, result in st.session_state.last_cmd_results.items():
            show_cmd_result(result)
    else:
        st.markdown(
            '<div style="text-align:center; padding:30px; color:#2a3040;">'
            '<div style="font-size:2rem;">⚙️</div>'
            '<div style="margin-top:8px; font-size:0.9rem; color:#4a5568;">Run a command above to see results here.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with st.expander("ℹ️ Command Details & CWD", expanded=False):
        for key, spec in SAFE_COMMANDS.items():
            st.markdown(f"""
**{spec['icon']} {spec['label']}** (`{key}`)
- CWD: `{spec['cwd']}`
- CMD: `{' '.join(spec['cmd'])}`
- Timeout: `{spec.get('timeout', 60)}s`
""")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — FILE EXPLORER
# ═════════════════════════════════════════════════════════════════════════════

with tab_files:
    st.markdown('<div class="card-title">📂 File Explorer — Allowed Paths Only</div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:0.82rem; color:#64748b; margin-bottom:12px;">'
        '🔒 Secret and credential files (.env, .pem, id_rsa, etc.) are always blocked — '
        'even if they exist under an allowed root.'
        '</p>',
        unsafe_allow_html=True,
    )

    # Quick-access buttons
    st.markdown('<div style="font-size:0.8rem; color:#64748b; margin-bottom:8px;">Quick access:</div>', unsafe_allow_html=True)
    quick_cols = st.columns(len(ALLOWED_ROOTS))
    for i, root in enumerate(ALLOWED_ROOTS):
        with quick_cols[i]:
            if st.button(f"📁 {root.name}", key=f"quick_root_{i}", use_container_width=True):
                st.session_state["explorer_path"] = str(root)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Directory Listing
    st.markdown("**📁 List Folder**")
    explorer_path = st.text_input(
        "Folder path",
        value=st.session_state.get("explorer_path", str(ALLOWED_ROOTS[0])),
        key="folder_input",
        label_visibility="collapsed",
        placeholder="Enter absolute path…",
    )

    if st.button("📋 List Folder", key="btn_list_folder"):
        entries, err = list_directory(explorer_path)
        if err:
            st.error(err)
        else:
            st.session_state["dir_entries"]    = entries
            st.session_state["dir_listed_for"] = explorer_path

    if "dir_entries" in st.session_state and st.session_state.get("dir_listed_for"):
        listed_for = st.session_state["dir_listed_for"]
        entries    = st.session_state["dir_entries"]
        st.markdown(
            f'<div style="font-size:0.78rem; color:#64748b; margin:8px 0;">'
            f'📂 <strong>{safe_html(listed_for)}</strong> — {len(entries)} items'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        <div style="display:flex; gap:12px; padding:6px 12px; font-size:0.75rem;
                    color:#64748b; font-weight:600; letter-spacing:0.06em;
                    border-bottom:1px solid #1e2330; margin-bottom:4px;">
          <span style="flex:1;">NAME</span>
          <span style="min-width:50px;">TYPE</span>
          <span style="min-width:90px; text-align:right;">SIZE</span>
        </div>
        """, unsafe_allow_html=True)

        for entry in entries:
            icon = "📁" if entry["type"] == "DIR" else "📄"
            size_str = fmt_size(entry["size"])
            is_blocked = entry.get("blocked", False)
            name_class = "file-name file-name-blocked" if is_blocked else "file-name"
            blocked_label = " 🔒" if is_blocked else ""
            name_safe = safe_html(entry["name"])
            st.markdown(f"""
            <div class="file-row">
              <span>{icon}</span>
              <span class="{name_class}">{name_safe}{blocked_label}</span>
              <span class="file-type">{entry['type']}</span>
              <span class="file-size">{size_str}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # File Reader
    st.markdown("**📖 Read File + Add to Context**")

    file_read_path = st.text_input(
        "File path",
        key="file_read_input",
        label_visibility="collapsed",
        placeholder="Enter absolute file path…",
    )

    max_lines_col, btn_col = st.columns([1, 2])
    with max_lines_col:
        max_lines = st.number_input(
            "Max lines",
            min_value=10,
            max_value=MAX_FILE_READ_LINES,
            value=200,
            step=50,
            key="max_lines_input",
        )
    with btn_col:
        read_clicked  = st.button("📖 Read + Add to Context", key="btn_read_file", use_container_width=True)
        read_only_btn = st.button("👁️ Preview Only (no context)", key="btn_read_only", use_container_width=True)

    if read_clicked or read_only_btn:
        fp = file_read_path.strip()
        if not fp:
            st.warning("Enter a file path first.")
        else:
            lines, err = read_file(fp, max_lines=int(max_lines))
            if err:
                st.error(err)
            else:
                total_shown = len(lines)
                if read_clicked:
                    chunk = make_context_chunk_from_file(fp, lines)
                    source_key = f"file:{fp}"
                    # Deduplicate: remove existing chunk for same file
                    st.session_state.context_chunks = [
                        c for c in st.session_state.context_chunks
                        if c["source"] != source_key
                    ]
                    add_context(source_key, chunk)
                    st.success(f"✅ Added {total_shown} lines from `{safe_html(fp)}` to agent context.")

                with st.expander(f"📄 {safe_html(fp)} — {total_shown} lines", expanded=True):
                    numbered = "\n".join(f"{i+1:04d}: {l}" for i, l in enumerate(lines))
                    st.code(numbered, language="text")


    st.markdown("<hr>", unsafe_allow_html=True)

    # ── File Range Reader ─────────────────────────────────────────────────────
    st.markdown("**🎯 File Range Reader** — Read specific line range")
    st.markdown(
        '<p style="font-size:0.82rem; color:#64748b; margin-bottom:10px;">'
        'Read only a specific range of lines (1-indexed). Same safety guards as full file reader.'
        '</p>',
        unsafe_allow_html=True,
    )

    range_path = st.text_input(
        "File path (range)",
        key="range_file_input",
        label_visibility="collapsed",
        placeholder="Enter absolute file path for range read…",
    )
    rc1, rc2, rc3 = st.columns([1, 1, 2])
    with rc1:
        range_start = st.number_input("Start Line", min_value=1, value=1, step=1, key="range_start")
    with rc2:
        range_end = st.number_input("End Line", min_value=1, value=50, step=10, key="range_end")
    with rc3:
        range_read_btn = st.button("🎯 Read Range + Add to Context", key="btn_range_read", use_container_width=True)
        range_preview_btn = st.button("👁️ Preview Range Only", key="btn_range_preview", use_container_width=True)

    if range_read_btn or range_preview_btn:
        rfp = range_path.strip()
        if not rfp:
            st.warning("Enter a file path first.")
        elif range_end < range_start:
            st.warning("End line must be ≥ start line.")
        else:
            sliced, err = read_file_range(rfp, int(range_start), int(range_end))
            if err:
                st.error(err)
            else:
                shown = len(sliced)
                label = f"L{range_start}–L{range_end}"
                if range_read_btn:
                    range_chunk = (
                        f"FILE (range {label}): {rfp}\n"
                        + "\n".join(f"{range_start + i:04d}: {l}" for i, l in enumerate(sliced))
                    )
                    source_key = f"file:{rfp}:{label}"
                    st.session_state.context_chunks = [
                        c for c in st.session_state.context_chunks
                        if c["source"] != source_key
                    ]
                    add_context(source_key, range_chunk)
                    st.success(f"✅ Added {shown} lines ({label}) from `{safe_html(rfp)}` to context.")
                with st.expander(f"📄 {safe_html(rfp)} — {label} ({shown} lines)", expanded=True):
                    numbered = "\n".join(f"{range_start + i:04d}: {l}" for i, l in enumerate(sliced))
                    st.code(numbered, language="text")


    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Git Diff Viewer ───────────────────────────────────────────────────────
    st.markdown("**🔀 Git Diff Viewer**")
    st.markdown(
        '<p style="font-size:0.82rem; color:#64748b; margin-bottom:10px;">'
        'Runs <code>git diff HEAD</code> on the OCR project (read-only). '
        'Output is shown as a colored diff and can be added to agent context.'
        '</p>',
        unsafe_allow_html=True,
    )

    gd_col1, gd_col2 = st.columns(2)
    with gd_col1:
        run_diff_btn = st.button("🔀 Run Git Diff + View", key="btn_git_diff", use_container_width=True)
    with gd_col2:
        run_log_btn = st.button("📜 Git Log (Last 10)", key="btn_git_log", use_container_width=True)

    if run_diff_btn:
        with st.spinner("Running git diff HEAD…"):
            diff_result = run_cmd_and_add("git-diff-full")
        ok = diff_result["exit_code"] == 0 and not diff_result["error"]
        if ok:
            raw_diff = diff_result["output"]
            # Strip the STDOUT: header if present
            if raw_diff.startswith("STDOUT:\n"):
                raw_diff = raw_diff[len("STDOUT:\n"):]
            line_count = raw_diff.count("\n")
            st.success(f"✅ Diff loaded — {line_count} diff lines | Added to agent context.")
            with st.expander("🔀 Git Diff Output", expanded=True):
                st.code(raw_diff, language="diff")
        else:
            st.error(f"Git diff failed (exit {diff_result['exit_code']}):")
            st.code(diff_result["output"], language="text")

    if run_log_btn:
        with st.spinner("Running git log…"):
            log_result = run_cmd_and_add("git-log-short")
        ok = log_result["exit_code"] == 0 and not log_result["error"]
        if ok:
            raw_log = log_result["output"]
            if raw_log.startswith("STDOUT:\n"):
                raw_log = raw_log[len("STDOUT:\n"):]
            st.success("✅ Git log loaded — added to agent context.")
            with st.expander("📜 Git Log (Last 10 Commits)", expanded=True):
                st.code(raw_log, language="text")
        else:
            st.error(f"Git log failed: {log_result['output']}")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — CONTEXT
# ═════════════════════════════════════════════════════════════════════════════

with tab_context:
    st.markdown('<div class="card-title">📋 Agent Context</div>', unsafe_allow_html=True)

    n_chunks  = len(st.session_state.context_chunks)
    ctx_chars = context_size_chars()
    ctx_pct   = min(100, int(ctx_chars / MAX_CONTEXT_CHARS_WARN * 100)) if MAX_CONTEXT_CHARS_WARN else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Context Chunks", f"{n_chunks} / {MAX_CONTEXT_CHUNKS}")
    m2.metric("Approximate Size", fmt_size(ctx_chars))
    m3.metric("Size vs Warn Limit", f"{ctx_pct}%")
    m4.metric("Max Chunks Sent to LLM", "8")

    if ctx_chars > MAX_CONTEXT_CHARS_WARN:
        st.warning(
            f"⚠️ Context is large (~{fmt_size(ctx_chars)}). "
            "Consider removing old chunks to keep agent answers focused.",
            icon="⚠️",
        )

    st.markdown("<hr>", unsafe_allow_html=True)

    col_clear, _ = st.columns([1, 3])
    with col_clear:
        if st.button("🗑️ Clear All Context", key="btn_clear_ctx"):
            st.session_state.context_chunks = []
            st.session_state.cmd_context_keys = set()
            st.rerun()

    if not st.session_state.context_chunks:
        st.markdown(
            '<div style="text-align:center; padding:30px; color:#2a3040;">'
            '<div style="font-size:2rem;">📋</div>'
            '<div style="margin-top:8px; font-size:0.9rem; color:#4a5568;">No context loaded yet.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        for idx, chunk in enumerate(st.session_state.context_chunks):
            source = chunk["source"]
            chunk_type = "📊 CMD" if source.startswith("cmd:") else "📄 FILE"
            size_str = fmt_size(len(chunk["content"]))
            label = f"Chunk {idx+1} — {chunk_type} · {safe_html(source)} · {size_str}"
            with st.expander(label, expanded=False):
                col_content, col_del = st.columns([5, 1])
                with col_content:
                    preview = chunk["content"][:600]
                    if len(chunk["content"]) > 600:
                        preview += "\n… [truncated in preview]"
                    st.code(preview, language="text")
                with col_del:
                    if st.button("❌ Remove", key=f"del_chunk_{idx}"):
                        removed_source = st.session_state.context_chunks[idx]["source"]
                        st.session_state.context_chunks.pop(idx)
                        st.session_state.cmd_context_keys.discard(removed_source)
                        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 — PROJECT AUDIT
# ═════════════════════════════════════════════════════════════════════════════

with tab_audit:
    st.markdown('<div class="card-title">🔎 One-Click Project Audit Workflows</div>', unsafe_allow_html=True)
    st.markdown("""
    <p style="font-size:0.85rem; color:#64748b; margin-bottom:20px;">
    Runs pre-approved commands in sequence and asks the agent to summarise
    <strong>only</strong> what the command outputs confirm. No hallucination.
    </p>
    """, unsafe_allow_html=True)

    # ── Quick Audit ──────────────────────────────────────────────────────────
    st.markdown("### ⚡ Quick Audit")
    st.markdown("""
    <div class="workflow-step"><div class="step-num">1</div> Run <code>git status --short</code></div>
    <div class="workflow-step"><div class="step-num">2</div> Run <code>python -m compileall app</code></div>
    <div class="workflow-step"><div class="step-num">3</div> Ask agent to summarise based only on command results</div>
    """, unsafe_allow_html=True)

    if st.button("▶️ Run Quick Audit", key="btn_quick_audit"):
        progress = st.progress(0, text="Step 1/3: Git Status…")
        r1 = run_cmd_and_add("git-status")
        progress.progress(33, text="Step 2/3: Python Compile…")
        r2 = run_cmd_and_add("compile")
        progress.progress(66, text="Step 3/3: Asking agent…")
        audit_q = (
            "Based ONLY on the git-status and compile command results in your context, "
            "give a quick project audit: what changed, any compile errors, and one safe next step."
        )
        audit_ans = None
        if st.session_state.ollama_ok and st.session_state.model_ok:
            audit_ans = ask_agent(audit_q)
            st.session_state.chat_history.append({"role": "user",  "text": f"[Quick Audit] {audit_q}"})
            st.session_state.chat_history.append({"role": "agent", "text": audit_ans})
        progress.progress(100, text="Done ✅")

        st.subheader("Results")
        show_cmd_result(r1)
        show_cmd_result(r2)
        if audit_ans:
            with st.expander("🤖 Agent Summary", expanded=True):
                st.markdown(audit_ans)
        else:
            st.warning("Ollama not running or model missing — agent summary skipped.")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Test Audit ───────────────────────────────────────────────────────────
    st.markdown("### 🧪 Test Audit")
    st.markdown("""
    <div class="workflow-step"><div class="step-num">1</div> Run <code>git status --short</code></div>
    <div class="workflow-step"><div class="step-num">2</div> Run <code>python -m compileall app</code></div>
    <div class="workflow-step"><div class="step-num">3</div> Run <code>pytest -q</code></div>
    <div class="workflow-step"><div class="step-num">4</div> Ask agent to summarise pass/fail and one next step</div>
    """, unsafe_allow_html=True)
    st.warning(
        "⚠️ **Pytest can take several minutes.** Only click if you want the full test suite.",
        icon="⏱️",
    )

    if st.button("▶️ Run Test Audit (includes Pytest)", key="btn_test_audit"):
        progress = st.progress(0, text="Step 1/4: Git Status…")
        r1 = run_cmd_and_add("git-status")
        progress.progress(25, text="Step 2/4: Compile…")
        r2 = run_cmd_and_add("compile")
        progress.progress(50, text="Step 3/4: Pytest (may take time)…")
        r3 = run_cmd_and_add("pytest")
        progress.progress(75, text="Step 4/4: Agent Summary…")
        audit_q = (
            "Based ONLY on the git-status, compile, and pytest results in context, "
            "summarise: how many tests passed/failed, any compile errors, and one safe next step."
        )
        audit_ans = None
        if st.session_state.ollama_ok and st.session_state.model_ok:
            audit_ans = ask_agent(audit_q)
            st.session_state.chat_history.append({"role": "user",  "text": f"[Test Audit] {audit_q}"})
            st.session_state.chat_history.append({"role": "agent", "text": audit_ans})
        progress.progress(100, text="Done ✅")

        st.subheader("Results")
        show_cmd_result(r1)
        show_cmd_result(r2)
        show_cmd_result(r3)
        if audit_ans:
            with st.expander("🤖 Agent Summary", expanded=True):
                st.markdown(audit_ans)
        else:
            st.warning("Ollama not running or model missing — agent summary skipped.")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Frontend Audit ───────────────────────────────────────────────────────
    st.markdown("### 🌐 Frontend Audit")
    st.markdown("""
    <div class="workflow-step"><div class="step-num">1</div> Run <code>node tests/check_js.js</code></div>
    <div class="workflow-step"><div class="step-num">2</div> Ask agent to summarise frontend status</div>
    """, unsafe_allow_html=True)

    if st.button("▶️ Run Frontend Audit", key="btn_frontend_audit"):
        progress = st.progress(0, text="Step 1/2: Frontend JS Check…")
        r1 = run_cmd_and_add("frontend-check")
        progress.progress(50, text="Step 2/2: Agent Summary…")
        audit_q = (
            "Based ONLY on the frontend-check output in context, "
            "what is the frontend status? List any JS errors and one safe next step."
        )
        audit_ans = None
        if st.session_state.ollama_ok and st.session_state.model_ok:
            audit_ans = ask_agent(audit_q)
            st.session_state.chat_history.append({"role": "user",  "text": f"[Frontend Audit] {audit_q}"})
            st.session_state.chat_history.append({"role": "agent", "text": audit_ans})
        progress.progress(100, text="Done ✅")

        st.subheader("Results")
        show_cmd_result(r1)
        if audit_ans:
            with st.expander("🤖 Agent Summary", expanded=True):
                st.markdown(audit_ans)
        else:
            st.warning("Ollama not running or model missing — agent summary skipped.")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Test Failure Analyzer ─────────────────────────────────────────────────
    st.markdown("### 🧬 Test Failure Analyzer")
    st.markdown("""
    <p style="font-size:0.85rem; color:#64748b; margin-bottom:12px;">
    Runs <code>pytest -q</code>, then parses FAILED/ERROR lines and asks the agent
    to suggest one safe fix per failure. All grounded — no hallucination.
    </p>
    <div class="workflow-step"><div class="step-num">1</div> Run <code>pytest -q</code></div>
    <div class="workflow-step"><div class="step-num">2</div> Parse FAILED / ERROR lines from output</div>
    <div class="workflow-step"><div class="step-num">3</div> Ask agent for one safe fix per failure</div>
    """, unsafe_allow_html=True)
    st.warning(
        "⚠️ **Pytest can take several minutes.** Only click if you want the full test suite.",
        icon="⏱️",
    )

    if st.button("🧬 Run Test Failure Analyzer", key="btn_test_failure_analyzer"):
        progress = st.progress(0, text="Step 1/3: Running pytest…")
        pytest_result = run_cmd_and_add("pytest")
        progress.progress(50, text="Step 2/3: Parsing failures…")

        raw_out = pytest_result.get("output", "")
        # Parse FAILED and ERROR lines from pytest output
        failure_lines = []
        for line in raw_out.splitlines():
            stripped = line.strip()
            if stripped.startswith("FAILED ") or stripped.startswith("ERROR "):
                failure_lines.append(stripped)

        progress.progress(75, text="Step 3/3: Agent analysis…")

        st.subheader("📊 Pytest Raw Result")
        show_cmd_result(pytest_result)

        st.subheader("🔍 Parsed Failures")
        if not failure_lines:
            st.success("✅ No FAILED or ERROR lines found in pytest output — all tests may have passed!")
        else:
            st.error(f"❌ {len(failure_lines)} failure(s) detected:")
            # Render failure table
            st.markdown("""
            <div style="background:#0d1117; border:1px solid #1e2330; border-radius:8px; padding:16px; margin:8px 0;">
              <div style="display:flex; gap:12px; font-size:0.75rem; color:#64748b; font-weight:600;
                          letter-spacing:0.06em; border-bottom:1px solid #1e2330; margin-bottom:8px; padding-bottom:6px;">
                <span style="min-width:50px;">#</span>
                <span style="flex:1;">TEST / ERROR</span>
              </div>
            """, unsafe_allow_html=True)
            for i, fl in enumerate(failure_lines):
                tag = "FAILED" if fl.startswith("FAILED") else "ERROR"
                color = "#ef4444" if tag == "FAILED" else "#f59e0b"
                name = safe_html(fl[len(tag):].strip())
                st.markdown(f"""
              <div style="display:flex; gap:12px; padding:6px 0; border-bottom:1px solid #111822;
                          font-family:'JetBrains Mono',monospace; font-size:0.8rem;">
                <span style="min-width:50px; color:#64748b;">{i+1}</span>
                <span>
                  <span style="color:{color}; font-weight:700;">[{tag}]</span>
                  <span style="color:#cbd5e1;"> {name}</span>
                </span>
              </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Ask agent for fix suggestions
            failure_summary = "\n".join(failure_lines)
            fix_q = (
                f"Based ONLY on the pytest output in context, these tests failed:\n{failure_summary}\n\n"
                "For each failure, give one safe next step to investigate or fix it. "
                "Do not invent causes — only use what is visible in the output."
            )
            if st.session_state.ollama_ok and st.session_state.model_ok:
                with st.spinner("🤖 Agent analyzing failures…"):
                    fix_ans = ask_agent(fix_q)
                st.session_state.chat_history.append({"role": "user",  "text": f"[Test Failure Analyzer] {fix_q}"})
                st.session_state.chat_history.append({"role": "agent", "text": fix_ans})
                with st.expander("🤖 Agent Fix Suggestions", expanded=True):
                    st.markdown(fix_ans)
            else:
                st.warning("Ollama not running or model missing — agent fix suggestions skipped.")

        progress.progress(100, text="Done ✅")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Full Safe Audit ───────────────────────────────────────────────────────
    st.markdown("### 🚀 Full Safe Audit")
    st.markdown("""
    <p style="font-size:0.85rem; color:#64748b; margin-bottom:12px;">
    Runs <strong>every</strong> safe command in sequence, then asks the agent for a
    comprehensive project health summary. Results are deduplicated in context.
    </p>
    """, unsafe_allow_html=True)

    all_cmd_keys = list(SAFE_COMMANDS.keys())
    for i, ck in enumerate(all_cmd_keys):
        spec = SAFE_COMMANDS[ck]
        st.markdown(
            f'<div class="workflow-step"><div class="step-num">{i+1}</div> '
            f'{spec["icon"]} {safe_html(spec["label"])} — <code>{" ".join(spec["cmd"])}</code></div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div class="workflow-step"><div class="step-num">{len(all_cmd_keys)+1}</div> '
        f'🤖 Agent full project summary</div>',
        unsafe_allow_html=True,
    )
    st.warning(
        "⚠️ **Full Audit includes Pytest.** This may take several minutes.",
        icon="⏱️",
    )

    if st.button("🚀 Run Full Safe Audit (All Commands)", key="btn_full_audit"):
        total_steps = len(all_cmd_keys) + 1
        all_results = {}
        for idx, ck in enumerate(all_cmd_keys):
            spec = SAFE_COMMANDS[ck]
            pct = int(idx / total_steps * 100)
            progress = st.progress(pct, text=f"Step {idx+1}/{total_steps}: {spec['label']}…")
            r = run_cmd_and_add(ck)
            all_results[ck] = r

        progress = st.progress(int(len(all_cmd_keys) / total_steps * 100), text="Final step: Agent full summary…")
        full_audit_q = (
            "Based ONLY on ALL the command results now in your context "
            "(git status, git diff, git log, compile, pytest, frontend check, backend health, directory listing), "
            "give a comprehensive project health report:\n"
            "1. Confirmed facts from each command\n"
            "2. Any failures or warnings found\n"
            "3. Overall project health rating (Healthy / Needs Attention / Critical)\n"
            "4. One safe next step\n"
            "Do NOT invent anything not in the command outputs."
        )
        full_audit_ans = None
        if st.session_state.ollama_ok and st.session_state.model_ok:
            full_audit_ans = ask_agent(full_audit_q)
            st.session_state.chat_history.append({"role": "user",  "text": f"[Full Safe Audit] {full_audit_q}"})
            st.session_state.chat_history.append({"role": "agent", "text": full_audit_ans})
        progress.progress(100, text="Full Audit Done ✅")

        st.subheader("📋 All Command Results")
        for ck, res in all_results.items():
            show_cmd_result(res)

        if full_audit_ans:
            with st.expander("🤖 Agent Full Project Summary", expanded=True):
                st.markdown(full_audit_ans)
        else:
            st.warning("Ollama not running or model missing — full audit agent summary skipped.")

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Export Audit Report ───────────────────────────────────────────────────
    st.markdown("### 📥 Export Audit Report")
    st.markdown("""
    <p style="font-size:0.85rem; color:#64748b; margin-bottom:12px;">
    Downloads a timestamped plain-text report containing all current context chunks,
    command results, and the last 10 chat messages. <strong>Nothing is written to disk by the agent.</strong>
    </p>
    """, unsafe_allow_html=True)

    def _build_audit_report() -> str:
        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "=" * 70,
            "AGENT ALINE X — AUDIT REPORT",
            f"Generated: {now_str}",
            "=" * 70,
            "",
            f"CONTEXT CHUNKS ({len(st.session_state.context_chunks)} loaded)",
            "-" * 70,
        ]
        for i, chunk in enumerate(st.session_state.context_chunks):
            lines.append(f"\n--- Chunk {i+1}: {chunk['source']} ---")
            lines.append(chunk["content"])

        lines += [
            "",
            "=" * 70,
            f"COMMAND RESULTS THIS SESSION ({len(st.session_state.last_cmd_results)} commands)",
            "-" * 70,
        ]
        for key, res in st.session_state.last_cmd_results.items():
            status = "✅ OK" if res["exit_code"] == 0 and not res["error"] else "❌ FAILED"
            lines.append(f"\n[{status}] {res['label']} ({key}) | exit={res['exit_code']} | {res.get('duration_ms',0)}ms")
            lines.append(f"CMD: {res['cmd_str']}")
            lines.append(res["output"])

        history = st.session_state.chat_history[-10:]
        lines += [
            "",
            "=" * 70,
            f"CHAT HISTORY (last {len(history)} messages)",
            "-" * 70,
        ]
        for msg in history:
            role = "YOU" if msg["role"] == "user" else "AGENT ALINE X"
            lines.append(f"\n[{role}]")
            lines.append(msg["text"])

        lines += ["", "=" * 70, "END OF REPORT", "=" * 70]
        return "\n".join(lines)

    import datetime as _dt
    report_filename = f"aline_x_audit_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    report_ready = (
        bool(st.session_state.context_chunks)
        or bool(st.session_state.last_cmd_results)
        or bool(st.session_state.chat_history)
    )

    if report_ready:
        report_content = _build_audit_report()
        st.download_button(
            label="📥 Download Audit Report (.txt)",
            data=report_content.encode("utf-8"),
            file_name=report_filename,
            mime="text/plain",
            key="btn_export_report",
            use_container_width=True,
        )
        st.caption(
            f"Report will include {len(st.session_state.context_chunks)} context chunks, "
            f"{len(st.session_state.last_cmd_results)} command results, "
            f"and {min(len(st.session_state.chat_history), 10)} chat messages."
        )
    else:
        st.info(
            "ℹ️ Run some commands or load files first — the report will include "
            "whatever context and results are currently loaded in this session.",
            icon="📋",
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 6 — SAFETY PANEL
# ═════════════════════════════════════════════════════════════════════════════

with tab_safety:
    st.markdown('<div class="card-title">🛡️ Safety Configuration — v1.1</div>', unsafe_allow_html=True)

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("""
        <div class="card">
          <div class="card-title">✅ Allowed Read Roots</div>
          <div class="safety-item"><span class="safety-icon">📁</span><code>D:\\AGENT_ALINE_X_</code></div>
          <div class="safety-item"><span class="safety-icon">📁</span><code>D:\\OCR_MASTER\\ocr-platform-complete</code></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="card">
          <div class="card-title">✍️ Write Access</div>
          <div class="safety-item">
            <span class="safety-icon">✅</span>
            <div><code>D:\\AGENT_ALINE_X_</code> — Read + Write</div>
          </div>
          <div class="safety-item">
            <span class="safety-icon">👁️</span>
            <div><code>D:\\OCR_MASTER\\ocr-platform-complete</code> — Read-Only</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="card">
          <div class="card-title">🔒 Patch Mode</div>
          <div class="safety-item">
            <span class="safety-icon">🔴</span>
            <div><strong style="color:#ef4444;">PATCH MODE: OFF</strong><br>
            OCR project files cannot be modified. Enable explicitly when ready.</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="card">
          <div class="card-title">🚫 No Free Terminal</div>
          <div class="safety-item">
            <span class="safety-icon">🔒</span>
            <div>No arbitrary command textbox exists in this UI.<br>
            Only the predefined Safe Commands buttons are allowed.</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col_r:
        st.markdown("""
        <div class="card">
          <div class="card-title">🚫 Blocked Paths</div>
          <div class="safety-item"><span class="safety-icon">🚫</span><code>C:\\</code> — Entire C drive</div>
          <div class="safety-item"><span class="safety-icon">🚫</span><code>C:\\Users\\*</code> — All user profiles</div>
          <div class="safety-item"><span class="safety-icon">🚫</span><code>*\\Desktop\\*</code></div>
          <div class="safety-item"><span class="safety-icon">🚫</span><code>*\\Downloads\\*</code></div>
          <div class="safety-item"><span class="safety-icon">🚫</span><code>*\\Documents\\*</code></div>
          <div class="safety-item"><span class="safety-icon">🚫</span><code>*\\AppData\\*</code></div>
          <div class="safety-item"><span class="safety-icon">🚫</span><code>*.ssh\\*</code> — SSH keys</div>
          <div class="safety-item"><span class="safety-icon">🚫</span><code>*\\secrets\\*</code></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="card">
          <div class="card-title">🔒 Blocked Secret Files (v1.1 NEW)</div>
          <div class="safety-item"><span class="safety-icon">🔒</span><code>.env</code> and all variants</div>
          <div class="safety-item"><span class="safety-icon">🔒</span><code>id_rsa</code>, <code>id_ed25519</code>, <code>id_ecdsa</code></div>
          <div class="safety-item"><span class="safety-icon">🔒</span><code>*.pem</code>, <code>*.key</code>, <code>*.p12</code>, <code>*.pfx</code></div>
          <div class="safety-item"><span class="safety-icon">🔒</span><code>secrets.json/yaml</code>, <code>credentials.json</code></div>
          <div class="safety-item"><span class="safety-icon">🔒</span><code>token.json</code>, <code>service_account.json</code></div>
          <div class="safety-item"><span class="safety-icon">🔒</span>Shown in listing as 🔒 — contents never readable</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="card">
          <div class="card-title">🚫 Blocked Command Categories</div>
          <div class="safety-item"><span class="safety-icon">🚫</span>git add / commit / push / reset / clean</div>
          <div class="safety-item"><span class="safety-icon">🚫</span>Remove-Item / rm / del / rmdir</div>
          <div class="safety-item"><span class="safety-icon">🚫</span>docker prune / docker rm / docker rmi</div>
          <div class="safety-item"><span class="safety-icon">🚫</span>Any arbitrary shell command</div>
          <div class="safety-item"><span class="safety-icon">🚫</span>Write to OCR project (patch mode off)</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="card" style="border-color: rgba(239,68,68,0.2); background: rgba(239,68,68,0.04);">
      <div class="card-title" style="color:#ef4444;">⚠️ Security Notice — v1.1</div>
      <p style="font-size:0.88rem; color:#cbd5e1; margin:0;">
        v1.1 adds: XSS protection on all chat messages (HTML-escaped before rendering),
        secret file blocking in file explorer (even under allowed roots),
        command deduplication in context, and context size warnings.
        No arbitrary terminal. No secret file reads. Patch mode stays OFF.
      </p>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📋 Full Allowed Command List", expanded=False):
        for key, spec in SAFE_COMMANDS.items():
            st.markdown(f"""
| Field | Value |
|-------|-------|
| Key | `{key}` |
| Label | {spec['icon']} {spec['label']} |
| CWD | `{spec['cwd']}` |
| Command | `{' '.join(spec['cmd'])}` |
| Timeout | `{spec.get('timeout', 60)}s` |
""")
            st.markdown("---")
