import {
  Bot,
  Bug,
  ClipboardCheck,
  Code2,
  FileSearch,
  GitBranch,
  Hammer,
  History,
  NotebookTabs,
  PackageCheck,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";
import type { AgentMode, FileItem, MemoryItem, ModelKey, SafeCommand, WorkflowStep } from "./types";

export const availableModels: ModelKey[] = [
  "auto",
  "agent-aline-x",
  "maxwellb/gemma4-12b-it-oym",
  "qwen2.5-coder:7b",
];

export const allowedRoots = [
  "D:/AGENT_ALINE_X_",
  "D:/OCR_MASTER/ocr-platform-complete",
];

export const agentModes: AgentMode[] = [
  {
    key: "architect",
    label: "Architect",
    tone: "text-honey",
    icon: NotebookTabs,
    directive: "Requirements, scope, risks, and clean plans.",
  },
  {
    key: "builder",
    label: "Builder",
    tone: "text-agent",
    icon: Hammer,
    directive: "Small patches, typed code, and practical UI work.",
  },
  {
    key: "tester",
    label: "Tester",
    tone: "text-mint",
    icon: ClipboardCheck,
    directive: "Verification, regression checks, and failure analysis.",
  },
  {
    key: "reporter",
    label: "Reporter",
    tone: "text-iris",
    icon: FileSearch,
    directive: "Client-ready summaries and handoff notes.",
  },
];

export const workspaceFiles: FileItem[] = [
  {
    id: "agent-ui",
    name: "agent_ui.py",
    path: "D:/AGENT_ALINE_X_/agent_ui.py",
    language: "Python",
    status: "modified",
    lines: 1480,
    content: `st.set_page_config(
    page_title="AGENT ALINE X",
    page_icon="AI",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    active_model = st.selectbox(
        "Model",
        AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(DEFAULT_MODEL),
    )
    temperature = st.slider("Temperature", 0.0, 1.0, 0.1)

tab_chat, tab_commands, tab_files, tab_context = st.tabs([
    "Agent Chat",
    "Safe Commands",
    "File Explorer",
    "Context",
])

if prompt := st.chat_input("Ask with loaded context"):
    answer = ollama_chat(
        prompt=prompt,
        model=active_model,
        context=st.session_state.context_chunks,
        temperature=temperature,
    )`,
  },
  {
    id: "agent-tools",
    name: "agent_tools.py",
    path: "D:/AGENT_ALINE_X_/agent_tools.py",
    language: "Python",
    status: "clean",
    lines: 420,
    content: `def run_safe_command(command_key: str) -> CommandResult:
    config = SAFE_COMMANDS.get(command_key)
    if config is None:
        return CommandResult(False, "", "Unknown command", 0.0)

    started = time.perf_counter()
    completed = subprocess.run(
        config["cmd"],
        cwd=config["cwd"],
        shell=False,
        capture_output=True,
        text=True,
        timeout=config["timeout"],
    )

    return CommandResult(
        ok=completed.returncode == 0,
        stdout=truncate_output(completed.stdout),
        stderr=truncate_output(completed.stderr),
        duration=time.perf_counter() - started,
    )`,
  },
  {
    id: "agent-config",
    name: "agent_config.py",
    path: "D:/AGENT_ALINE_X_/agent_config.py",
    language: "Python",
    status: "locked",
    lines: 260,
    content: `MODEL_NAME = "agent-aline-x"
DEFAULT_MODEL = "qwen2.5-coder:7b"

ALLOWED_ROOTS = [
    Path("D:/AGENT_ALINE_X_").resolve(),
    Path("D:/OCR_MASTER/ocr-platform-complete").resolve(),
]

WRITE_ALLOWED_ROOTS = [
    Path("D:/AGENT_ALINE_X_").resolve(),
]

MAX_CONTEXT_CHUNKS = 12
MAX_COMMAND_OUTPUT_CHARS = 8000
MAX_FILE_READ_LINES = 500`,
  },
  {
    id: "readme-ui",
    name: "README_AGENT_UI.md",
    path: "D:/AGENT_ALINE_X_/README_AGENT_UI.md",
    language: "Markdown",
    status: "clean",
    lines: 190,
    content: `# AGENT ALINE X Browser UI

Professional local coding/project agent UI powered by Streamlit + Ollama.

Daily flow:
1. Start Ollama.
2. Run the agent UI.
3. Load project context.
4. Run safe commands.
5. Ask the agent with grounded context.`,
  },
  {
    id: "react-app",
    name: "App.tsx",
    path: "D:/AGENT_ALINE_X_/frontend/src/App.tsx",
    language: "TypeScript React",
    status: "new",
    lines: 760,
    content: `type AgentWorkbench = {
  modes: ["Architect", "Builder", "Tester", "Reporter"];
  flow: ["Audit", "Plan", "Patch", "Verify", "Report"];
  panels: ["Context", "Commands", "Trace", "Chat"];
};

const promise = "Real workbench UI, ready for backend hooks.";`,
  },
];

export const safeCommands: SafeCommand[] = [
  {
    id: "git-status",
    label: "Git Status",
    command: "git status --short",
    cwd: "D:/OCR_MASTER/ocr-platform-complete",
    timeout: "30s",
    intent: "See changed files before planning work.",
    icon: GitBranch,
  },
  {
    id: "git-diff-stat",
    label: "Git Diff Stat",
    command: "git diff --stat",
    cwd: "D:/OCR_MASTER/ocr-platform-complete",
    timeout: "30s",
    intent: "See size of uncommitted change before review.",
    icon: GitBranch,
  },
  {
    id: "git-diff-full",
    label: "Git Diff (Full)",
    command: "git diff HEAD",
    cwd: "D:/OCR_MASTER/ocr-platform-complete",
    timeout: "30s",
    intent: "Inspect exact uncommitted change content.",
    icon: GitBranch,
  },
  {
    id: "git-log-short",
    label: "Git Log",
    command: "git log --oneline -10",
    cwd: "D:/OCR_MASTER/ocr-platform-complete",
    timeout: "15s",
    intent: "Review recent commit history.",
    icon: History,
  },
  {
    id: "python-compile",
    label: "Python Compile",
    command: "python -m compileall app",
    cwd: "D:/OCR_MASTER/ocr-platform-complete",
    timeout: "60s",
    intent: "Catch syntax errors before patch handoff.",
    icon: Code2,
  },
  {
    id: "pytest",
    label: "Pytest",
    command: ".venv311/Scripts/python.exe -m pytest -q",
    cwd: "D:/OCR_MASTER/ocr-platform-complete",
    timeout: "300s",
    intent: "Run backend regression checks.",
    icon: Bug,
  },
  {
    id: "frontend-build",
    label: "Frontend Build",
    command: "npm run build",
    cwd: "D:/AGENT_ALINE_X_/frontend",
    timeout: "120s",
    intent: "Validate the frontend build compiles cleanly.",
    icon: PackageCheck,
  },
  {
    id: "backend-health",
    label: "Backend Health",
    command: "curl.exe http://127.0.0.1:8787/api/health",
    cwd: "D:/AGENT_ALINE_X_",
    timeout: "15s",
    intent: "Check AGENT ALINE X bridge health without mutating state.",
    icon: TerminalSquare,
  },
];

export const baseWorkflow: WorkflowStep[] = [
  {
    id: "audit",
    label: "Audit",
    detail: "Read context and run safe checks before action.",
    state: "idle",
  },
  {
    id: "plan",
    label: "Plan",
    detail: "Pick the smallest useful implementation path.",
    state: "idle",
  },
  {
    id: "patch",
    label: "Patch",
    detail: "Prepare focused file-level changes.",
    state: "idle",
  },
  {
    id: "verify",
    label: "Verify",
    detail: "Build, test, and capture residual risk.",
    state: "idle",
  },
  {
    id: "report",
    label: "Report",
    detail: "Summarize outcome in clear handoff form.",
    state: "idle",
  },
];

export const memoryItems: MemoryItem[] = [
  {
    id: "identity",
    label: "Identity",
    value: "AGENT ALINE X, local coding and project agent.",
    tone: "text-agent",
  },
  {
    id: "safety",
    label: "Safety",
    value: "Audit first, read-only first, no delete, no fake done.",
    tone: "text-honey",
  },
  {
    id: "language",
    label: "Language",
    value: "Tanglish + English, practical and direct.",
    tone: "text-mint",
  },
  {
    id: "models",
    label: "Models",
    value: "qwen2.5-coder:7b, agent-aline-x, Gemma 12B OYM.",
    tone: "text-iris",
  },
];

export const reportTemplates = [
  {
    label: "Daily Status",
    body: "Completed, blocked, next P0, risks, verification.",
    icon: Bot,
  },
  {
    label: "Release Readiness",
    body: "Build status, test status, open risks, go/no-go checklist.",
    icon: ShieldCheck,
  },
  {
    label: "Bug Investigation",
    body: "Repro steps, root cause, evidence, fix plan, rollback note.",
    icon: Bug,
  },
  {
    label: "Test Failure Summary",
    body: "Failed cases, error output, suspected cause, retest plan.",
    icon: ClipboardCheck,
  },
];
