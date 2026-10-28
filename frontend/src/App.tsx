// App.tsx — AGENT ALINE X Web v3.3 (Release Freeze)
// API wiring, command IDs, safety checks, mock fallback: unchanged from v2.2.

import {
  Activity,
  AlertTriangle,
  Bot,
  Boxes,
  Bug,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Circle,
  ClipboardCheck,
  Code2,
  Command,
  Copy,
  Database,
  Download,
  FileCode2,
  Files,
  Folder,
  FolderOpen,
  GitBranch,
  Hammer,
  History,
  LayoutDashboard,
  Loader2,
  Lock,
  NotebookTabs,
  PanelRightOpen,
  Play,
  Plus,
  Radio,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  SquareTerminal,
  TestTube2,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { FormEvent, RefObject, useEffect, useMemo, useRef, useState } from "react";
import {
  agentModes,
  allowedRoots,
  availableModels,
  baseWorkflow,
  memoryItems,
  reportTemplates,
  safeCommands,
  workspaceFiles,
} from "./data";
import {
  buildAgentReply,
  createCommandRun,
  findFileById,
  formatTime,
  makeWorkflowState,
} from "./agentRuntime";
import {
  fetchHealth,
  fetchModels,
  postChat,
  runCommandBridge,
  runFullAuditBridge,
  testModelBridge,
  listFiles,
  readFileRange,
  fetchQASnapshot,
  fetchQAReport,
  searchProject,
} from "./apiClient";
import type { BridgeHealth, BridgeQASnapshot, BridgeQAReport, FileEntry, FileLine, ProjectSearchResult } from "./apiClient";
import type {
  AgentModeKey,
  AuditEvent,
  ChatContextChunk,
  ChatMessage,
  CommandRun,
  FailureAnalysis,
  FileItem,
  HealthRating,
  ModelKey,
  ResponseLength,
  SafeCommand,
  WorkflowStep,
  WorkspaceView,
} from "./types";

// ─── Nav items ─────────────────────────────────────────────────────────────
const viewItems: Array<{ key: WorkspaceView; label: string; icon: LucideIcon }> = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "agent", label: "Chat", icon: Bot },
  { key: "files", label: "Workspace", icon: Files },
  { key: "audit", label: "Audit", icon: ShieldCheck },
  { key: "commands", label: "Commands", icon: SquareTerminal },
  { key: "reports", label: "Reports", icon: NotebookTabs },
  { key: "safety", label: "Safety", icon: Lock },
  { key: "settings", label: "Settings", icon: Settings },
];

const stateClass: Record<WorkflowStep["state"], string> = {
  idle: "border-line text-zinc-600",
  running: "border-agent/60 bg-agent/8 text-agent",
  done: "border-mint/40 bg-mint/5 text-mint",
  blocked: "border-tomato/40 text-tomato",
};

const fileTone: Record<FileItem["status"], string> = {
  clean: "text-zinc-500",
  modified: "text-agent",
  locked: "text-honey",
  new: "text-iris",
};

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

const MAX_CHAT_CONTEXT_CHUNKS = 6;
const MAX_CHAT_CONTEXT_CHARS = 18000;
const MAX_RANGE_CONTEXT_LINES = 160;
const LOCAL_GREETING_WORDS = new Set(["hi", "hello", "hey", "vanakkam", "ready", "yo", "hai"]);
const MEMORY_CONTEXT_TERMS = [
  "search project memory",
  "project memory",
  "memory search",
  "search files",
  "find files",
  "explain files involved",
  "model router",
  "route model",
  "router",
  "backend_bridge",
  "project context",
  "codebase",
  "file involved",
  "files involved",
];

function isLocalGreetingPrompt(prompt: string) {
  const cleaned = prompt.trim().toLowerCase().replace(/[!?.]+$/g, "");
  if (LOCAL_GREETING_WORDS.has(cleaned)) return true;
  const words = cleaned.split(/\s+/).filter(Boolean);
  return words.length <= 3 && words.some((word) => LOCAL_GREETING_WORDS.has(word));
}

function isMemoryContextPrompt(prompt: string) {
  const low = prompt.toLowerCase();
  return MEMORY_CONTEXT_TERMS.some((term) => low.includes(term));
}

function formatDuration(ms?: number) {
  if (ms === undefined) return null;
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;
}

function buildCommandContext(run: CommandRun): string {
  return [
    `COMMAND RESULT: ${run.label} (${run.commandId})`,
    `Exit code: ${run.exitCode}`,
    `Duration: ${run.duration}`,
    run.output,
  ].join("\n");
}

// ─── Root component ─────────────────────────────────────────────────────────
function ChatMetaBadges({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") return null;
  const sourceLabel =
    msg.answerSource === "fast_local"
      ? "Fast local answer"
      : msg.answerSource === "model"
        ? "Model answer"
        : msg.answerSource === "mock"
          ? "Mock answer"
          : null;
  const duration = formatDuration(msg.durationMs);
  const badges = [sourceLabel, duration, msg.responseLength, msg.status].filter((badge): badge is string => Boolean(badge));

  return (
    <div className="flex flex-wrap items-center gap-1">
      {badges.map((badge) => (
        <span key={badge} className="rounded border border-line bg-[#0f0e0d] px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-zinc-500">
          {badge}
        </span>
      ))}
      {msg.selectedModel && (
        <span className="rounded border border-line bg-[#0f0e0d] px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-zinc-400">
          Model: {msg.selectedModel}
        </span>
      )}
      {msg.routeReason && (
        <span className="rounded border border-line bg-[#0f0e0d] px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-zinc-500">
          Route: {msg.routeReason}
        </span>
      )}
      {msg.fallbackUsed && (
        <span className="rounded border border-amber-600/40 bg-amber-900/20 px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-amber-400">
          Fallback
        </span>
      )}
      {msg.contextTrimmed && (
        <span className="rounded border border-amber-600/40 bg-amber-900/20 px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-amber-400">
          Context trimmed
        </span>
      )}
      {msg.fileContextUsed && (
        <span className="rounded border border-line bg-[#0f0e0d] px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-zinc-400" title={`${msg.fileContextChars} chars`}>
          Files: {msg.fileContextFileCount}
        </span>
      )}
      {msg.fileContextTrimmed && (
        <span className="rounded border border-amber-600/40 bg-amber-900/20 px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-amber-400">
          File context trimmed
        </span>
      )}
      {msg.memoryContextUsed && (
        <span className="rounded border border-line bg-[#0f0e0d] px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-zinc-400" title={`${msg.memoryContextChars ?? 0} chars`}>
          Memory: {msg.retrievalMode || "keyword"}
        </span>
      )}
      {(msg.memoryContextUsed || (msg.memoryContextChunks ?? 0) > 0) && (
        <span className="rounded border border-line bg-[#0f0e0d] px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-zinc-400">
          Chunks: {msg.memoryContextChunks ?? 0}
        </span>
      )}
      {msg.memoryIndexMissing && (
        <span className="rounded border border-amber-600/40 bg-amber-900/20 px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-amber-400">
          Index missing
        </span>
      )}
      {msg.memoryAutoReindexed && (
        <span className="rounded border border-mint/40 bg-mint/10 px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-mint">
          Reindexed
        </span>
      )}
    </div>
  );
}

export default function App() {
  const [activeView, setActiveView] = useState<WorkspaceView>("dashboard");
  const [mode, setMode] = useState<AgentModeKey>("builder");
  const [objective, setObjective] = useState("Create a full React TS Tailwind agent workbench");
  const [selectedFileId, setSelectedFileId] = useState(workspaceFiles[0].id);
  const [loadedFileIds, setLoadedFileIds] = useState<string[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowStep[]>(baseWorkflow);
  const [chatInput, setChatInput] = useState("");
  const [chatRunning, setChatRunning] = useState(false);
  const [auditRunning, setAuditRunning] = useState(false);
  const [cycleRunning, setCycleRunning] = useState(false);
  const [commandRunningId, setCommandRunningId] = useState<string | null>(null);
  const [modelTestRunning, setModelTestRunning] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);
  const [traceOpen, setTraceOpen] = useState(true);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState("");
  const [commandRuns, setCommandRuns] = useState<CommandRun[]>([]);
  const [activeModel, setActiveModel] = useState<ModelKey>("auto");
  const [responseLength, setResponseLength] = useState<ResponseLength>("Balanced");
  const [temperature, setTemperature] = useState(0.1);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [healthRating, setHealthRating] = useState<HealthRating | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [backendHealth, setBackendHealth] = useState<BridgeHealth | null>(null);
  const [qaSnapshot, setQaSnapshot] = useState<BridgeQASnapshot | null>(null);
  const [qaSnapshotLoading, setQaSnapshotLoading] = useState(false);

  // Custom states for upgraded visual experience
  const [auditActiveStep, setAuditActiveStep] = useState<number>(0);

  // File Explorer state
  const [explorerPath, setExplorerPath] = useState(allowedRoots[0]);
  const [explorerInput, setExplorerInput] = useState(allowedRoots[0]);
  const [explorerEntries, setExplorerEntries] = useState<FileEntry[]>([]);
  const [explorerError, setExplorerError] = useState<string | null>(null);
  const [explorerLoading, setExplorerLoading] = useState(false);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewLines, setPreviewLines] = useState<FileLine[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewStart, setPreviewStart] = useState(1);
  const [previewEnd, setPreviewEnd] = useState(80);
  const [previewDurationMs, setPreviewDurationMs] = useState<number | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [rangeContextChunks, setRangeContextChunks] = useState<ChatContextChunk[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);


  const [logs, setLogs] = useState<string[]>([
    "[agent] workbench ready",
    "[safety] audit first, read-only first",
    "[frontend] React + TypeScript + Tailwind",
  ]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      role: "agent",
      text: "Vanakkam. Real agent workbench ready. Load context, run checks, then I can plan, patch, verify, and report.",
      time: formatTime(),
    },
  ]);

  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const workflowTimers = useRef<number[]>([]);

  const selectedFile = useMemo(() => findFileById(selectedFileId), [selectedFileId]);
  const loadedFiles = useMemo(() => loadedFileIds.map(findFileById), [loadedFileIds]);
  const activeMode = useMemo(() => agentModes.find((item) => item.key === mode) ?? agentModes[0], [mode]);
  const contextScore = Math.min(
    100,
    rangeContextChunks.length * 24 + commandRuns.length * 14 + loadedFiles.length * 6 + workflow.filter((s) => s.state === "done").length * 6,
  );
  const lastCommand = commandRuns[0];
  const commandRunning = commandRunningId !== null;
  const isRunning = chatRunning || auditRunning || cycleRunning || commandRunning || modelTestRunning;
  const groundedContextChunks = useMemo(() => {
    const commandContext = commandRuns.slice(0, 4).map(buildCommandContext);
    return [...rangeContextChunks.map((chunk) => chunk.text), ...commandContext];
  }, [rangeContextChunks, commandRuns]);

  // Key bindings
  useEffect(() => {
    const onKeyDown = (e: globalThis.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
      if (e.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages, isRunning]);

  // Collapse right panel on dashboard, open on other primary workspaces by default
  useEffect(() => {
    if (activeView === "dashboard") {
      setRightOpen(false);
    } else if (activeView === "files" || activeView === "commands" || activeView === "audit") {
      setRightOpen(true);
    }
  }, [activeView]);

  // Cleanup timers
  useEffect(() => {
    return () => workflowTimers.current.forEach(window.clearTimeout);
  }, []);

  // Backend health poll
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const health = await fetchHealth();
      if (cancelled) return;
      setBackendOnline(health !== null);
      setBackendHealth(health);
      if (health) {
        const models = await fetchModels();
        if (!cancelled && models && models.models.length > 0) {
          setActiveModel((current) =>
            models.models.includes(current) ? current : (models.default_model as ModelKey),
          );
        }
      }
    };
    poll();
    const interval = window.setInterval(poll, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const addLog = (line: string) => {
    setLogs((c) => [`[${formatTime()}] ${line}`, ...c].slice(0, 80));
  };

  const pushMessage = (role: "user" | "agent" | "system", text: string, meta: Partial<ChatMessage> = {}) => {
    setMessages((c) => {
      const normalized = text.trim();
      if (c.length > 0) {
        const last = c[c.length - 1];
        if (last.role === role && last.text.trim() === normalized) {
          return c;
        }
      }
      if (role !== "user" && c.slice(-8).some((msg) => msg.role === role && msg.text.trim() === normalized)) {
        return c;
      }
      return [
        ...c,
        {
          id: Date.now() + Math.random(),
          role,
          text,
          time: formatTime(),
          durationMs: meta.durationMs,
          answerSource: meta.answerSource,
          responseLength: meta.responseLength,
          status: meta.status,
          selectedModel: meta.selectedModel,
          routeReason: meta.routeReason,
          fallbackUsed: meta.fallbackUsed,
          contextTrimmed: meta.contextTrimmed,
          fileContextUsed: meta.fileContextUsed,
          fileContextFileCount: meta.fileContextFileCount,
          fileContextChars: meta.fileContextChars,
          fileContextTrimmed: meta.fileContextTrimmed,
          memoryContextUsed: meta.memoryContextUsed,
          memoryContextChunks: meta.memoryContextChunks,
          retrievalMode: meta.retrievalMode,
          memoryContextChars: meta.memoryContextChars,
          memoryIndexMissing: meta.memoryIndexMissing,
          memoryAutoReindexed: meta.memoryAutoReindexed,
          memoryResultsFound: meta.memoryResultsFound,
        },
      ];
    });
  };

  const toggleLoadedFile = (fileId: string) => {
    setLoadedFileIds((c) => {
      if (c.includes(fileId)) {
        addLog(`context removed: ${findFileById(fileId).name}`);
        return c.filter((id) => id !== fileId);
      }
      addLog(`context loaded: ${findFileById(fileId).name}`);
      return [...c, fileId];
    });
  };

  const loadFolder = (rawPath: string) => {
    const path = rawPath.trim();
    if (!path) return;
    setExplorerLoading(true);
    setExplorerError(null);
    listFiles(path).then((result) => {
      setExplorerLoading(false);
      if (!result) {
        setExplorerError("Backend bridge offline. Start RUN_WEB_V2.ps1.");
        setExplorerEntries([]);
        return;
      }
      if (result.error) {
        setExplorerError(result.error);
        setExplorerEntries([]);
        addLog(`workspace: blocked/failed — ${result.error}`);
        return;
      }
      const resolved = result.path ?? path;
      setExplorerPath(resolved);
      setExplorerInput(resolved);
      setExplorerEntries(result.entries);
      addLog(`workspace: listed ${result.entries.length} entries`);
    });
  };

  const openPreview = (rawPath: string, start = 1, end = 80) => {
    setPreviewLoading(true);
    setPreviewError(null);
    const t0 = performance.now();
    readFileRange(rawPath, start, end).then((result) => {
      const ms = Math.round(performance.now() - t0);
      setPreviewLoading(false);
      setPreviewDurationMs(ms);
      if (!result) {
        setPreviewError("Backend bridge offline. Start RUN_WEB_V2.ps1.");
        setPreviewLines([]);
        return;
      }
      if (result.error) {
        setPreviewError(result.error);
        setPreviewLines([]);
        setPreviewPath(rawPath);
        addLog(`workspace: blocked/failed read — ${result.error}`);
        return;
      }
      setPreviewPath(result.path ?? rawPath);
      setPreviewLines(result.lines);
      setPreviewStart(start);
      setPreviewEnd(end);
      addLog(`workspace: previewed (lines ${start}–${end})`);
    });
  };

  const addPreviewToChatContext = () => {
    if (!previewPath || previewLines.length === 0) {
      pushMessage("system", "No range loaded. Read a file range first.");
      return;
    }

    const limitedLines = previewLines.slice(0, MAX_RANGE_CONTEXT_LINES);
    const start = limitedLines[0]?.line ?? previewStart;
    const end = limitedLines[limitedLines.length - 1]?.line ?? previewEnd;
    const id = `${previewPath.toLowerCase()}#${start}-${end}`;
    const body = limitedLines.map((entry) => `${String(entry.line).padStart(4, "0")}: ${entry.text}`).join("\n");
    const text = [
      "FILE RANGE CONTEXT",
      `Path: ${previewPath}`,
      `Lines: ${start}-${end}`,
      "",
      body,
    ].join("\n");

    let added = false;
    let duplicate = false;
    const chunk: ChatContextChunk = {
      id,
      label: `${previewPath.split(/[\\/]/).pop() ?? previewPath}:${start}-${end}`,
      path: previewPath,
      start,
      end,
      text,
      addedAt: formatTime(),
    };

    setRangeContextChunks((current) => {
      if (current.some((item) => item.id === id)) {
        duplicate = true;
        return current;
      }
      added = true;
      const next = [...current, chunk].slice(-MAX_CHAT_CONTEXT_CHUNKS);
      while (next.reduce((sum, item) => sum + item.text.length, 0) > MAX_CHAT_CONTEXT_CHARS && next.length > 1) {
        next.shift();
      }
      return next;
    });

    if (duplicate) {
      pushMessage("system", `Range already in chat context: ${chunk.label}`);
      return;
    }
    if (added) {
      pushMessage("system", `Added to chat context: ${chunk.label}`);
      addLog(`context added: ${chunk.label}`);
    }
  };

  const runCommand = (command: SafeCommand) => {
    if (commandRunning) return;
    addLog(`safe command queued: ${command.label}`);
    setCommandRunningId(command.id);

    if (backendOnline) {
      runCommandBridge(command.id).then((result) => {
        if (!result) {
          addLog(`safe command failed: ${command.label}`);
          setCommandRunningId(null);
          return;
        }
        const run: CommandRun = {
          id: Date.now(),
          commandId: command.id,
          label: result.label,
          exitCode: result.exit_code,
          duration: `${(result.duration_ms / 1000).toFixed(2)}s`,
          output: result.output,
          time: formatTime(),
          failureAnalysis: result.failure_analysis ?? null,
        };
        setCommandRuns((c) => [run, ...c].slice(0, 8));
        addLog(`safe command done: ${command.label} exit ${run.exitCode}`);
        pushMessage("system", `${run.label} — exit ${run.exitCode} (${run.duration})`);
        setCommandRunningId(null);
      });
      return;
    }

    addLog("mock mode: backend offline");
    window.setTimeout(() => {
      const run = createCommandRun(command.id);
      setCommandRuns((c) => [run, ...c].slice(0, 8));
      addLog(`safe command done: ${command.label} exit ${run.exitCode}`);
      pushMessage("system", `${run.label} — exit ${run.exitCode} (Mock Mode)`);
      setCommandRunningId(null);
    }, 650);
  };

  const runFullAudit = () => {
    if (auditRunning) return;
    setAuditRunning(true);
    setAuditActiveStep(1);
    addLog("full safe audit started");
    setAuditEvents((c) =>
      [{ id: Date.now(), label: "Full Safe Audit", detail: "started", time: formatTime() }, ...c].slice(0, 30),
    );

    if (backendOnline) {
      const stepTimer = window.setInterval(() => {
        setAuditActiveStep((step) => (step < 6 ? step + 1 : step));
      }, 350);

      runFullAuditBridge().then((result) => {
        window.clearInterval(stepTimer);
        if (!result) {
          addLog("full safe audit: no response");
          setAuditActiveStep(0);
          setAuditRunning(false);
          return;
        }
        result.steps.forEach((step) => {
          const run: CommandRun = {
            id: Date.now() + Math.random(),
            commandId: step.command_id,
            label: step.label,
            exitCode: step.exit_code,
            duration: `${(step.duration_ms / 1000).toFixed(2)}s`,
            output: step.output,
            time: formatTime(),
            failureAnalysis: step.failure_analysis ?? null,
          };
          setCommandRuns((c) => [run, ...c].slice(0, 8));
          setAuditEvents((c) =>
            [
              { id: Date.now() + Math.random(), label: step.label, detail: `exit ${step.exit_code}`, time: formatTime() },
              ...c,
            ].slice(0, 30),
          );
        });
        setHealthRating(result.health_rating);
        setAuditEvents((c) =>
          [
            {
              id: Date.now() + 999,
              label: "Full Safe Audit",
              detail: `complete — ${result.health_rating}`,
              time: formatTime(),
            },
            ...c,
          ].slice(0, 30),
        );
        addLog(`full safe audit complete: ${result.health_rating}`);
        setAuditActiveStep(7);
        setAuditRunning(false);
      });
      return;
    }

    addLog("mock mode: backend offline, using mock audit");
    safeCommands.slice(0, 6).forEach((command, index) => {
      window.setTimeout(() => {
        const run = createCommandRun(command.id);
        setCommandRuns((c) => [run, ...c].slice(0, 8));
        setAuditEvents((c) =>
          [
            { id: Date.now() + index, label: run.label, detail: `exit ${run.exitCode}`, time: formatTime() },
            ...c,
          ].slice(0, 30),
        );
        addLog(`audit step: ${run.label} exit ${run.exitCode}`);
        setAuditActiveStep(index + 2);
        
        if (index === 5) {
          const rating: HealthRating = "Healthy";
          setHealthRating(rating);
          setAuditEvents((c) =>
            [
              { id: Date.now() + 999, label: "Full Safe Audit", detail: `complete (Mock) — ${rating}`, time: formatTime() },
              ...c,
            ].slice(0, 30),
          );
          addLog(`full safe audit complete: ${rating} (Mock Mode)`);
          setAuditActiveStep(7);
          setAuditRunning(false);
        }
      }, (index + 1) * 500);
    });
  };

  const runAgentCycle = () => {
    if (cycleRunning) return;
    workflowTimers.current.forEach(window.clearTimeout);
    workflowTimers.current = [];
    setCycleRunning(true);
    addLog("demo cycle started (UI only — not a real verification)");
    setWorkflow(makeWorkflowState(0));

    [1, 2, 3, 4].forEach((stepIndex) => {
      const timer = window.setTimeout(() => {
        setWorkflow(makeWorkflowState(stepIndex));
        addLog(`agent step: ${["plan", "patch", "verify", "report"][stepIndex - 1]}`);
      }, stepIndex * 650);
      workflowTimers.current.push(timer);
    });

    const doneTimer = window.setTimeout(() => {
      const run = createCommandRun("frontend-build");
      setCommandRuns((c) => [run, ...c].slice(0, 8));
      setWorkflow(makeWorkflowState(5, true));
      pushMessage("agent", "Demo cycle complete. This is a UI workflow simulation only — not a real verification. Use Full Safe Audit for real validation.");
      addLog("demo cycle complete (UI simulation only)");
      setCycleRunning(false);
    }, 3600);
    workflowTimers.current.push(doneTimer);
  };

  const submitChat = (event?: FormEvent, customPrompt?: string) => {
    event?.preventDefault();
    const prompt = (customPrompt || chatInput).trim();
    if (!prompt || chatRunning) return;

    const filesToAttach = selectedFiles;
    pushMessage("user", prompt);
    if (!customPrompt) {
      setChatInput("");
      setSelectedFiles([]);
    }
    setChatRunning(true);
    addLog(`chat: ${prompt.slice(0, 56)}`);

    // Guard: Project status without context must say “Run Quick Audit first”
    const promptLower = prompt.toLowerCase();
    const isStatusQuery = ["project status", "status of project", "current status", "current state", "risk", "audit", "build", "git", "test"].some((term) =>
      promptLower.includes(term),
    );
    const isMemoryQuery = isMemoryContextPrompt(prompt);
    const hasContext = groundedContextChunks.length > 0;
    if (isLocalGreetingPrompt(prompt)) {
      pushMessage(
        "agent",
        "Vanakkam! AGENT ALINE X is ready. Ask a normal question, or run Quick Audit before project-status, risk, build, git, or test questions.",
        { durationMs: 0, answerSource: "fast_local", responseLength },
      );
      addLog("agent response generated (fast local)");
      setChatRunning(false);
      return;
    }

    if (isStatusQuery && !hasContext && !isMemoryQuery) {
      pushMessage("agent", "Not checked yet. Run Quick Audit first.", {
        durationMs: 0,
        answerSource: "fast_local",
        responseLength,
      });
      addLog("agent response generated (fast local)");
      setChatRunning(false);
      return;
    }

    if (backendOnline) {
      postChat({
        message: prompt,
        model: activeModel,
        context: groundedContextChunks,
        response_length: responseLength.toLowerCase(),
        temperature,
        selected_files: filesToAttach,
      }).then((result) => {
        const text = result ? result.response : "Backend bridge offline. Start RUN_WEB_V2.ps1.";
        pushMessage("agent", text, result ? {
          durationMs: result.duration_ms,
          answerSource: result.answer_source ?? (result.bypassed_ollama ? "fast_local" : "model"),
          responseLength: result.response_length ?? responseLength,
          status: result.error ? "error" : undefined,
          selectedModel: result.selected_model ?? result.metadata?.resolved_model,
          routeReason: result.route_reason ?? result.metadata?.route_reason,
          fallbackUsed: result.fallback_used ?? result.metadata?.fallback_used,
          contextTrimmed: result.metadata?.context_trimmed,
          fileContextUsed: result.metadata?.file_context_used,
          fileContextFileCount: result.metadata?.file_context_file_count,
          fileContextChars: result.metadata?.file_context_chars,
          fileContextTrimmed: result.metadata?.file_context_trimmed,
          memoryContextUsed: result.metadata?.memory_context_used,
          memoryContextChunks: result.metadata?.memory_context_chunks,
          retrievalMode: result.metadata?.retrieval_mode,
          memoryContextChars: result.metadata?.memory_context_chars,
          memoryIndexMissing: result.metadata?.memory_index_missing,
          memoryAutoReindexed: result.metadata?.memory_auto_reindexed,
          memoryResultsFound: result.metadata?.memory_results_found,
        } : { status: "offline" });
        addLog(result ? "agent response generated" : "chat failed: no response");
        setChatRunning(false);
      });
      return;
    }

    window.setTimeout(() => {
      pushMessage(
        "agent",
        `${buildAgentReply({ prompt, mode, objective, contextFiles: loadedFiles, lastCommand })} (Mock Mode)`,
        { durationMs: 700, answerSource: "mock", responseLength },
      );
      addLog("agent response generated (Mock Mode)");
      setChatRunning(false);
    }, 700);
  };

  const clearChat = () => {
    setMessages([
      {
        id: Date.now(),
        role: "agent",
        text: "Chat cleared. Add live file context, run a safe check, or ask a normal question.",
        time: formatTime(),
      },
    ]);
    setActiveModel("auto");
    addLog("chat cleared, model reset to auto");
  };

  const testActiveModel = () => {
    if (modelTestRunning) return;
    setModelTestRunning(true);
    pushMessage("system", `Testing active model: ${activeModel}`);
    if (backendOnline === false) {
      pushMessage("agent", "Backend bridge offline. Start RUN_WEB_V2.ps1, then test the model again.", { status: "offline" });
      setModelTestRunning(false);
      return;
    }
    testModelBridge(activeModel, temperature).then((result) => {
      if (!result) {
        pushMessage("agent", "Model test failed because the backend did not return a response.", { status: "failed" });
      } else if (result.ok) {
        pushMessage("agent", `Model test passed for ${result.model}.\n${result.message}`, {
          durationMs: result.duration_ms,
          answerSource: "model",
          status: result.status ?? "ready",
        });
      } else {
        pushMessage("agent", `Model test failed for ${result.model}.\n${result.message}`, {
          durationMs: result.duration_ms,
          answerSource: "model",
          status: result.status ?? "failed",
        });
      }
      setModelTestRunning(false);
    });
  };

  const triggerQuickPrompt = (promptText: string) => {
    if (chatRunning && promptText !== "Run Safe Audit" && promptText !== "Generate Daily Report") return;
    if (auditRunning && promptText === "Run Safe Audit") return;
    if (promptText === "Hi") {
      submitChat(undefined, "Hi");
    } else if (promptText === "Explain project") {
      submitChat(undefined, "Explain project");
    } else if (promptText === "Run Safe Audit") {
      runFullAudit();
      pushMessage("system", "Triggered Full Safe Audit flow");
    } else if (promptText === "Check risks") {
      submitChat(undefined, "Check risks");
    } else if (promptText === "Generate Daily Report") {
      setActiveView("reports");
      pushMessage("system", "Navigated to Reports page");
    }
  };

  const paletteCommands = [
    { label: "Demo Cycle (Non-Verifying)", detail: "UI workflow demo only — not a real audit or verification", icon: Zap, action: runAgentCycle },
    { label: "Run Full Safe Audit", detail: "All safe commands + health rating", icon: ShieldCheck, action: runFullAudit },
    { label: "Git Status", detail: "Safe command", icon: GitBranch, action: () => runCommand(safeCommands[0]) },
    {
      label: "Frontend Build",
      detail: "Safe command",
      icon: TestTube2,
      action: () => runCommand(safeCommands.find((c) => c.id === "frontend-build")!),
    },
    { label: "Toggle Agent Panel", detail: "Show/hide chat sidecar", icon: PanelRightOpen, action: () => setRightOpen((v) => !v) },
    { label: "Toggle Trace Panel", detail: "Show/hide bottom trace", icon: SquareTerminal, action: () => setTraceOpen((v) => !v) },
  ].filter((item) => `${item.label} ${item.detail}`.toLowerCase().includes(paletteQuery.toLowerCase()));

  return (
    <div className="flex h-screen min-h-[640px] flex-col overflow-hidden bg-shell text-zinc-100">
      {/* ── Top header ───────────────────────────────────────────────────── */}
      <TopBar
        activeMode={activeMode}
        contextScore={contextScore}
        activeModel={activeModel}
        setActiveModel={setActiveModel}
        onPalette={() => setPaletteOpen(true)}
        onToggleRight={() => setRightOpen((v) => !v)}
        onTestModel={testActiveModel}
        modelTestRunning={modelTestRunning}
        backendOnline={backendOnline}
        backendHealth={backendHealth}
      />

      {/* ── Offline banner ───────────────────────────────────────────────── */}
      {backendOnline === false && (
        <div className="flex h-7 shrink-0 items-center gap-2 border-b border-tomato/30 bg-tomato/8 px-4 text-[11px] font-medium text-tomato">
          <AlertTriangle className="h-3 w-3 shrink-0" />
          Backend bridge offline — start RUN_WEB_V2.ps1 · Showing Mock Mode data
        </div>
      )}

      {/* ── Main 3-zone layout ───────────────────────────────────────────── */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* Zone 1: Activity rail */}
        <ActivityRail activeView={activeView} onSelect={setActiveView} />

        {/* Zone 2: Left panel (Workspace File Explorer only) */}
        {activeView === "files" && (
          <LeftPanel
            activeView={activeView}
            selectedFileId={selectedFileId}
            loadedFileIds={loadedFileIds}
            onSelectFile={setSelectedFileId}
            onToggleLoadedFile={toggleLoadedFile}
            onRunCommand={runCommand}
            onSetMode={setMode}
            mode={mode}
            auditEvents={auditEvents}
            healthRating={healthRating}
            onRunFullAudit={runFullAudit}
            responseLength={responseLength}
            setResponseLength={setResponseLength}
            temperature={temperature}
            setTemperature={setTemperature}
            activeModel={activeModel}
            setActiveModel={setActiveModel}
            isRunning={isRunning}
            backendOnline={backendOnline}
            explorerPath={explorerPath}
            explorerInput={explorerInput}
            setExplorerInput={setExplorerInput}
            explorerEntries={explorerEntries}
            explorerError={explorerError}
            explorerLoading={explorerLoading}
            onLoadFolder={loadFolder}
            onOpenFile={(path) => {
              setActiveView("files");
              openPreview(path, 1, 80);
            }}
          />
        )}

        {/* Zone 3: Main content + bottom trace stacked */}
        <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-shell">
          {/* Workflow strip */}
          <WorkflowStrip
            objective={objective}
            setObjective={setObjective}
            workflow={workflow}
            onRun={runAgentCycle}
            isRunning={cycleRunning}
            activeView={activeView}
          />

          {/* Primary content pane */}
          <div className="min-h-0 flex-1 overflow-hidden">
            <MainPane
              activeView={activeView}
              selectedFile={selectedFile}
              loadedFiles={loadedFiles}
              commandRuns={commandRuns}
              backendOnline={backendOnline}
              previewPath={previewPath}
              previewLines={previewLines}
              previewError={previewError}
              previewLoading={previewLoading}
              previewStart={previewStart}
              previewEnd={previewEnd}
              previewDurationMs={previewDurationMs}
              setPreviewStart={setPreviewStart}
              setPreviewEnd={setPreviewEnd}
              onReadRange={(start, end) => previewPath && openPreview(previewPath, start, end)}
              onLoadRoot={() => {
                setActiveView("files");
                loadFolder(allowedRoots[0]);
              }}
              onRunAudit={runFullAudit}
              backendHealth={backendHealth}
              activeModel={activeModel}
              healthRating={healthRating}
              loadedFileIds={loadedFileIds}
              auditActiveStep={auditActiveStep}
              setActiveView={setActiveView}
              onRunCommand={runCommand}
              messages={messages}
              chatInput={chatInput}
              setChatInput={setChatInput}
              submitChat={submitChat}
              isRunning={
                activeView === "agent"
                  ? chatRunning
                  : activeView === "audit"
                    ? auditRunning
                    : activeView === "commands"
                      ? commandRunning
                      : cycleRunning
              }
              chatEndRef={chatEndRef}
              responseLength={responseLength}
              setResponseLength={setResponseLength}
              temperature={temperature}
              setTemperature={setTemperature}
              triggerQuickPrompt={triggerQuickPrompt}
              setActiveModel={setActiveModel}
              auditEvents={auditEvents}
              rangeContextChunks={rangeContextChunks}
              onAddRangeToContext={addPreviewToChatContext}
              onClearChat={clearChat}
              onTestModel={testActiveModel}
              modelTestRunning={modelTestRunning}
              qaSnapshot={qaSnapshot}
              qaSnapshotLoading={qaSnapshotLoading}
              onRefreshSnapshot={() => {
                if (qaSnapshotLoading) return;
                setQaSnapshotLoading(true);
                fetchQASnapshot().then((data) => {
                  setQaSnapshot(data);
                  setQaSnapshotLoading(false);
                });
              }}
              selectedFiles={selectedFiles}
              setSelectedFiles={setSelectedFiles}
            />
          </div>

          {/* Bottom trace panel (Workspace, Audit, and Commands only) */}
          {(activeView === "files" || activeView === "audit" || activeView === "commands") && (
            <TracePanel
              logs={logs}
              commandRuns={commandRuns}
              selectedFile={selectedFile}
              open={traceOpen}
              onToggle={() => setTraceOpen((v) => !v)}
            />
          )}
        </main>

        {/* Zone 4: Right agent chat (Hidden on Chat view to avoid duplication) */}
        {activeView !== "agent" && rightOpen && (
          <AgentSidecar
            activeMode={activeMode}
            mode={mode}
            setMode={setMode}
            messages={messages}
            chatInput={chatInput}
            setChatInput={setChatInput}
            submitChat={submitChat}
            isRunning={chatRunning}
            chatEndRef={chatEndRef}
            onRunCycle={runAgentCycle}
            onRunCommand={() => runCommand(safeCommands[0])}
            activeModel={activeModel}
          />
        )}
      </div>

      {/* Status bar */}
      <StatusBar activeView={activeView} selectedFile={selectedFile} commandRuns={commandRuns} contextScore={contextScore} />

      {/* Command palette */}
      {paletteOpen && (
        <CommandPalette
          query={paletteQuery}
          setQuery={setPaletteQuery}
          commands={paletteCommands}
          onClose={() => setPaletteOpen(false)}
        />
      )}
    </div>
  );
}

// ─── TopBar ─────────────────────────────────────────────────────────────────
function TopBar({
  activeMode,
  contextScore,
  onPalette,
  onToggleRight,
  onTestModel,
  modelTestRunning,
  activeModel,
  setActiveModel,
  backendOnline,
  backendHealth,
}: {
  activeMode: (typeof agentModes)[number];
  contextScore: number;
  onPalette: () => void;
  onToggleRight: () => void;
  onTestModel: () => void;
  modelTestRunning: boolean;
  activeModel: ModelKey;
  setActiveModel: (model: ModelKey) => void;
  backendOnline: boolean | null;
  backendHealth: BridgeHealth | null;
}) {
  const bridgeLabel =
    backendOnline === null ? "checking…" : backendOnline ? "Bridge: online" : "Bridge: offline";
  const bridgeTone =
    backendOnline === null ? "text-zinc-500" : backendOnline ? "text-mint" : "text-tomato";
  const ollamaLabel =
    backendOnline && backendHealth?.ollama === "ok" ? "Ollama: ok" : "Ollama: --";
  const ollamaTone = backendOnline && backendHealth?.ollama === "ok" ? "text-mint" : "text-zinc-500";

  return (
    <header className="thin-scrollbar flex h-10 shrink-0 items-center gap-2 overflow-x-auto border-b border-line bg-rail px-3">
      {/* Logo */}
      <div className="flex w-[190px] shrink-0 items-center gap-2 sm:w-[220px]">
        <div className="grid h-6 w-6 shrink-0 place-items-center rounded bg-agent/15 text-agent">
          <Boxes className="h-3.5 w-3.5" />
        </div>
        <span className="text-sm font-semibold text-zinc-100 tracking-wide">AGENT ALINE X</span>
        <span className="hidden rounded border border-line px-1 py-0.5 text-[10px] text-zinc-500 lg:block">v3.3</span>
      </div>

      {/* Command center (center) */}
      <button
        onClick={onPalette}
        className="mx-auto hidden h-7 w-[min(440px,38vw)] items-center gap-2 rounded border border-line bg-[#0f0e0d] px-2.5 text-left text-xs text-zinc-500 hover:border-agent/50 hover:text-zinc-300 transition-colors md:flex"
      >
        <Command className="h-3.5 w-3.5 shrink-0" />
        <span className="min-w-0 flex-1 truncate">Command center</span>
        <span className="shrink-0 rounded bg-[#0a0908] px-1 py-0.5 text-[10px] text-zinc-600">Ctrl K</span>
      </button>

      {/* Right badges */}
      <div className="flex shrink-0 items-center gap-1.5">
        <select
          value={activeModel}
          onChange={(e) => setActiveModel(e.target.value as ModelKey)}
          className="h-7 max-w-[190px] rounded border border-line bg-panel px-2 text-[11px] text-zinc-300 outline-none hover:border-agent/50 transition-colors"
          title="Active model"
        >
          {availableModels.map((m) => (
            <option key={m} value={m}>
              {m === "auto" ? "Auto Router" : m}
            </option>
          ))}
        </select>

        <button
          onClick={onTestModel}
          disabled={modelTestRunning}
          className="flex h-7 items-center gap-1.5 rounded border border-line bg-panel px-2 text-[11px] text-zinc-400 hover:border-agent/50 hover:text-agent disabled:cursor-not-allowed disabled:text-zinc-600 transition-colors"
          title="Test active model"
        >
          {modelTestRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <TestTube2 className="h-3.5 w-3.5" />}
          <span className="hidden lg:inline">Test Model</span>
        </button>

        <Chip icon={Radio} label={bridgeLabel} tone={bridgeTone} />
        <Chip icon={Radio} label={ollamaLabel} tone={ollamaTone} />
        <Chip icon={Lock} label="Patch Mode OFF" tone="text-honey" />

        <button
          onClick={onToggleRight}
          className="grid h-7 w-7 place-items-center rounded border border-line text-zinc-500 hover:border-agent/50 hover:text-zinc-100 transition-colors"
          title="Toggle agent panel"
        >
          <PanelRightOpen className="h-3.5 w-3.5" />
        </button>
      </div>
    </header>
  );
}

function Chip({ icon: Icon, label, tone }: { icon: LucideIcon; label: string; tone: string }) {
  return (
    <div className="flex h-7 items-center gap-1.5 rounded border border-line bg-panel px-2 text-[11px] text-zinc-400">
      <Icon className={cx("h-3 w-3 shrink-0", tone)} />
      <span className="hidden truncate lg:inline">{label}</span>
    </div>
  );
}

// ─── Activity Rail ───────────────────────────────────────────────────────────
function ActivityRail({ activeView, onSelect }: { activeView: WorkspaceView; onSelect: (view: WorkspaceView) => void }) {
  return (
    <nav className="flex w-[52px] shrink-0 flex-col items-center border-r border-line bg-[#181614] py-1.5 gap-0.5">
      {viewItems.map((item) => {
        const Icon = item.icon;
        const active = activeView === item.key;
        return (
          <button
            key={item.key}
            onClick={() => onSelect(item.key)}
            title={item.label}
            className={cx(
              "relative flex h-10 w-10 flex-col items-center justify-center gap-0.5 rounded text-[9px] transition-colors",
              active
                ? "bg-panel text-agent"
                : "text-zinc-600 hover:bg-panel/60 hover:text-zinc-300",
            )}
          >
            {active && <span className="absolute left-0 h-5 w-0.5 rounded-r bg-agent" />}
            <Icon className="h-4 w-4" />
            <span className="hidden truncate text-center xl:block">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

// ─── Left Panel ──────────────────────────────────────────────────────────────
function LeftPanel({
  activeView,
  selectedFileId,
  loadedFileIds,
  onSelectFile,
  onToggleLoadedFile,
  onRunCommand,
  onSetMode,
  mode,
  auditEvents,
  healthRating,
  onRunFullAudit,
  responseLength,
  setResponseLength,
  temperature,
  setTemperature,
  activeModel,
  setActiveModel,
  isRunning,
  backendOnline,
  explorerPath,
  explorerInput,
  setExplorerInput,
  explorerEntries,
  explorerError,
  explorerLoading,
  onLoadFolder,
  onOpenFile,
}: {
  activeView: WorkspaceView;
  selectedFileId: string;
  loadedFileIds: string[];
  onSelectFile: (id: string) => void;
  onToggleLoadedFile: (id: string) => void;
  onRunCommand: (cmd: SafeCommand) => void;
  onSetMode: (mode: AgentModeKey) => void;
  mode: AgentModeKey;
  auditEvents: AuditEvent[];
  healthRating: HealthRating | null;
  onRunFullAudit: () => void;
  responseLength: ResponseLength;
  setResponseLength: (v: ResponseLength) => void;
  temperature: number;
  setTemperature: (v: number) => void;
  activeModel: ModelKey;
  setActiveModel: (m: ModelKey) => void;
  isRunning: boolean;
  backendOnline: boolean | null;
  explorerPath: string;
  explorerInput: string;
  setExplorerInput: (v: string) => void;
  explorerEntries: FileEntry[];
  explorerError: string | null;
  explorerLoading: boolean;
  onLoadFolder: (path: string) => void;
  onOpenFile: (path: string) => void;
}) {
  return (
    <aside className="hidden w-[300px] shrink-0 flex-col border-r border-line bg-panel md:flex">
      {/* Panel title */}
      <div className="flex h-9 shrink-0 items-center border-b border-line px-3">
        <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-zinc-500">
          {viewItems.find((v) => v.key === activeView)?.label ?? activeView}
        </span>
      </div>

      {/* Panel body */}
      <div className="thin-scrollbar min-h-0 flex-1 overflow-auto">
        {/* ── Chat (mode selector) */}
        {activeView === "agent" && (
          <div className="space-y-1.5 p-3">
            <PanelSectionTitle>Agent Mode</PanelSectionTitle>
            {agentModes.map((item) => {
              const Icon = item.icon;
              const active = mode === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => onSetMode(item.key)}
                  className={cx(
                    "flex w-full items-center gap-2.5 rounded border px-3 py-2 text-left transition-colors",
                    active
                      ? "border-agent/40 bg-agent/8 text-zinc-100"
                      : "border-transparent text-zinc-400 hover:border-line hover:text-zinc-200",
                  )}
                >
                  <Icon className={cx("h-4 w-4 shrink-0", item.tone)} />
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{item.label}</div>
                    <div className="truncate text-[11px] text-zinc-500">{item.directive}</div>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* ── Workspace: context files + live explorer */}
        {activeView === "files" && (
          <div className="space-y-0 divide-y divide-line">
            {/* Context files section */}
            <div className="p-3">
              <PanelSectionTitle>Reference Files (demo only)</PanelSectionTitle>
              <div className="mt-2 space-y-0.5">
                {workspaceFiles.map((file) => {
                  const selected = selectedFileId === file.id;
                  const loaded = loadedFileIds.includes(file.id);
                  return (
                    <div
                      key={file.id}
                      className={cx(
                        "flex items-center gap-1 rounded",
                        selected && "bg-[#2a2724]",
                      )}
                    >
                      <button
                        onClick={() => onSelectFile(file.id)}
                        className="flex h-8 min-w-0 flex-1 items-center gap-2 rounded px-2 text-left text-xs text-zinc-300 hover:bg-panel2"
                      >
                        <FileCode2 className={cx("h-3.5 w-3.5 shrink-0", fileTone[file.status])} />
                        <span className="min-w-0 flex-1 truncate">{file.name}</span>
                        {file.status === "locked" && <Lock className="h-3 w-3 text-honey" />}
                      </button>
                      <button
                        onClick={() => onToggleLoadedFile(file.id)}
                        title={loaded ? "Remove from context" : "Add to context"}
                        className={cx(
                          "grid h-7 w-7 shrink-0 place-items-center rounded text-zinc-600 hover:bg-panel2 hover:text-zinc-100 transition-colors",
                          loaded && "text-agent",
                        )}
                      >
                        {loaded ? <Check className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Live file explorer section */}
            <div className="p-3">
              <PanelSectionTitle>Live File Explorer</PanelSectionTitle>
              <div className="mt-2 space-y-2">
                {/* Root shortcuts */}
                <div className="space-y-1">
                  {allowedRoots.map((root) => (
                    <button
                      key={root}
                      onClick={() => { setExplorerInput(root); onLoadFolder(root); }}
                      className="flex h-7 w-full items-center gap-2 rounded border border-line bg-[#1a1917] px-2 text-left text-[11px] text-zinc-400 hover:border-agent/40 hover:text-zinc-200 transition-colors"
                    >
                      <FolderOpen className="h-3 w-3 shrink-0 text-honey" />
                      <span className="min-w-0 flex-1 truncate font-mono">{root}</span>
                    </button>
                  ))}
                </div>

                {/* Path input + list */}
                <div className="flex items-center gap-1">
                  <input
                    value={explorerInput}
                    onChange={(e) => setExplorerInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") onLoadFolder(explorerInput); }}
                    placeholder="Folder path…"
                    className="h-7 min-w-0 flex-1 rounded border border-line bg-[#0f0e0d] px-2 font-mono text-[11px] text-zinc-200 outline-none focus:border-agent/50"
                  />
                  <button
                    onClick={() => onLoadFolder(explorerInput)}
                    className="flex h-7 shrink-0 items-center gap-1 rounded bg-agent px-2 text-[11px] font-semibold text-[#06211f] hover:bg-[#5eead4] transition-colors"
                  >
                    {explorerLoading ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Search className="h-3 w-3" />
                    )}
                    List
                  </button>
                </div>

                {/* Status / error */}
                {backendOnline === false && (
                  <p className="rounded border border-tomato/30 bg-tomato/8 px-2 py-1.5 text-[11px] text-tomato">
                    Backend offline — start RUN_WEB_V2.ps1
                  </p>
                )}
                {backendOnline !== false && explorerError && (
                  <div className="flex items-start gap-1.5 rounded border border-honey/30 bg-honey/8 px-2 py-1.5 text-[11px] text-honey">
                    <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                    <span className="break-words">{explorerError}</span>
                  </div>
                )}

                {/* Current path */}
                {explorerEntries.length > 0 && (
                  <div className="truncate font-mono text-[10px] text-zinc-600" title={explorerPath}>
                    {explorerPath}
                  </div>
                )}

                {/* Entries */}
                <div className="space-y-0.5">
                  {explorerEntries.length === 0 && !explorerError && backendOnline !== false && (
                    <p className="text-[11px] text-zinc-600">No entries — pick a root or enter a path.</p>
                  )}
                  {explorerEntries.map((entry) => {
                    const joinPath = `${explorerPath.replace(/[/\\]+$/, "")}/${entry.name}`;
                    const isLocked = entry.type === "FILE" && entry.locked;
                    return (
                      <button
                        key={entry.name}
                        disabled={isLocked}
                        onClick={() =>
                          entry.type === "DIR" ? onLoadFolder(joinPath) : onOpenFile(joinPath)
                        }
                        title={isLocked ? "Blocked: secret/credential file" : entry.name}
                        className={cx(
                          "flex h-7 w-full items-center gap-2 rounded px-2 text-left text-[11px] transition-colors",
                          isLocked
                            ? "cursor-not-allowed text-zinc-600"
                            : "text-zinc-300 hover:bg-panel2",
                        )}
                      >
                        {entry.type === "DIR" ? (
                          <Folder className="h-3.5 w-3.5 shrink-0 text-honey" />
                        ) : (
                          <FileCode2 className="h-3.5 w-3.5 shrink-0 text-zinc-500" />
                        )}
                        <span className="min-w-0 flex-1 truncate">{entry.name}</span>
                        {isLocked && <Lock className="h-3 w-3 shrink-0 text-honey" />}
                        {entry.type === "FILE" && entry.size != null && !isLocked && (
                          <span className="shrink-0 text-[10px] text-zinc-600">
                            {entry.size < 1024
                              ? `${entry.size}B`
                              : `${(entry.size / 1024).toFixed(0)}K`}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Commands */}
        {activeView === "commands" && (
          <div className="space-y-2 p-3">
            <PanelSectionTitle>Safe Commands</PanelSectionTitle>
            {safeCommands.map((cmd) => (
              <CommandCard key={cmd.id} command={cmd} onRun={() => onRunCommand(cmd)} />
            ))}
          </div>
        )}

        {/* ── Audit */}
        {activeView === "audit" && (
          <div className="space-y-3 p-3">
            <button
              onClick={onRunFullAudit}
              disabled={isRunning}
              className="flex h-9 w-full items-center justify-center gap-2 rounded bg-agent text-sm font-semibold text-[#06211f] disabled:cursor-not-allowed disabled:bg-line disabled:text-zinc-500 transition-colors"
            >
              {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              Run Full Safe Audit
            </button>

            {healthRating && (
              <div
                className={cx(
                  "rounded border px-3 py-2 text-xs font-semibold",
                  healthRating === "Healthy" && "border-mint/40 bg-mint/8 text-mint",
                  healthRating === "Needs Attention" && "border-honey/40 bg-honey/8 text-honey",
                  healthRating === "Critical" && "border-tomato/40 bg-tomato/8 text-tomato",
                )}
              >
                Health: {healthRating}
              </div>
            )}

            <div className="space-y-1.5">
              <PanelSectionTitle>Audit Steps</PanelSectionTitle>
              {safeCommands.slice(0, 6).map((cmd) => (
                <CommandCard key={cmd.id} command={cmd} onRun={() => onRunCommand(cmd)} compact />
              ))}
            </div>

            {auditEvents.length > 0 && (
              <div>
                <PanelSectionTitle>Timeline</PanelSectionTitle>
                <div className="thin-scrollbar mt-2 max-h-40 space-y-1 overflow-auto rounded border border-line bg-[#171614] p-2">
                  {auditEvents.map((ev) => (
                    <div key={ev.id} className="text-[11px] text-zinc-400">
                      <span className="text-zinc-600">{ev.time}</span>{" "}
                      <span className="text-zinc-300">{ev.label}</span>:{" "}
                      {ev.detail}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Memory */}
        {activeView === "memory" && (
          <div className="space-y-1.5 p-3">
            <PanelSectionTitle>Agent Memory</PanelSectionTitle>
            {memoryItems.map((item) => (
              <div key={item.id} className="rounded border border-line bg-[#1a1917] px-3 py-2">
                <div className={cx("text-[10px] font-semibold uppercase tracking-[0.12em]", item.tone)}>
                  {item.label}
                </div>
                <p className="mt-1 text-xs leading-4 text-zinc-300">{item.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* ── Reports */}
        {activeView === "reports" && (
          <div className="space-y-1.5 p-3">
            <PanelSectionTitle>Report Templates</PanelSectionTitle>
            {reportTemplates.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  className="flex w-full items-start gap-2.5 rounded border border-line bg-[#1a1917] px-3 py-2 text-left hover:border-agent/40 transition-colors"
                >
                  <Icon className="mt-0.5 h-4 w-4 shrink-0 text-agent" />
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-zinc-100">{item.label}</div>
                    <p className="mt-0.5 text-[11px] leading-4 text-zinc-500">{item.body}</p>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* ── Safety */}
        {activeView === "safety" && (
          <div className="space-y-1.5 p-3">
            <PanelSectionTitle>Safety Policy</PanelSectionTitle>
            {[
              { label: "Patch Mode", value: "OFF — no write endpoints", icon: Lock, tone: "text-honey" },
              { label: "Terminal", value: "Safe commands only, no free input", icon: ShieldCheck, tone: "text-mint" },
              { label: "Secrets", value: ".env, id_rsa, *.pem, keys — always blocked", icon: Lock, tone: "text-mint" },
              { label: "OCR Project", value: "Read-only", icon: ShieldCheck, tone: "text-mint" },
              { label: "Subprocess Policy", value: "shell=False, timeout enforced", icon: Code2, tone: "text-mint" },
              { label: "Future Patching", value: "Human approval required", icon: AlertTriangle, tone: "text-honey" },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.label} className="rounded border border-line bg-[#1a1917] px-3 py-2">
                  <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-500">
                    <Icon className={cx("h-3.5 w-3.5 shrink-0", item.tone)} />
                    {item.label}
                  </div>
                  <p className={cx("mt-1 text-xs leading-4", item.tone)}>{item.value}</p>
                </div>
              );
            })}
            <div className="mt-2">
              <PanelSectionTitle>Allowed Roots</PanelSectionTitle>
              <div className="mt-1 space-y-0.5">
                {allowedRoots.map((root) => (
                  <div key={root} className="font-mono text-[11px] text-zinc-400">{root}</div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Settings */}
        {activeView === "settings" && (
          <div className="space-y-4 p-3">
            <div>
              <PanelSectionTitle>Model</PanelSectionTitle>
              <select
                value={activeModel}
                onChange={(e) => setActiveModel(e.target.value as ModelKey)}
                className="mt-1.5 h-8 w-full rounded border border-line bg-[#1a1917] px-2 text-sm text-zinc-200 outline-none hover:border-agent/50"
              >
                {availableModels.map((m) => (
                  <option key={m} value={m}>{m === "auto" ? "Auto Router (best model)" : m}</option>
                ))}
              </select>
            </div>

            <div>
              <PanelSectionTitle>Response Length</PanelSectionTitle>
              <div className="mt-1.5 grid grid-cols-3 gap-1.5">
                {(["Quick", "Balanced", "Detailed"] as ResponseLength[]).map((rl) => (
                  <button
                    key={rl}
                    onClick={() => setResponseLength(rl)}
                    className={cx(
                      "rounded border py-1.5 text-xs font-medium transition-colors",
                      responseLength === rl
                        ? "border-agent/50 bg-agent/10 text-zinc-100"
                        : "border-line text-zinc-500 hover:border-zinc-600",
                    )}
                  >
                    {rl}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <PanelSectionTitle>Temperature</PanelSectionTitle>
                <span className="text-xs text-zinc-300">{temperature.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={temperature}
                onChange={(e) => setTemperature(Number(e.target.value))}
                className="mt-2 w-full accent-agent"
              />
              <p className="mt-1 text-[11px] text-zinc-600">Default 0.1 — grounded, low-variance.</p>
            </div>

            <div className="rounded border border-line bg-[#1a1917] px-3 py-2 text-[11px] text-zinc-500">
              Theme: Dark professional (fixed)
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function PanelSectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
      {children}
    </div>
  );
}

function CommandCard({ command, onRun, compact }: { command: SafeCommand; onRun: () => void; compact?: boolean }) {
  const Icon = command.icon;
  if (compact) {
    return (
      <div className="flex items-center gap-2 rounded border border-line bg-[#1a1917] px-2 py-1.5">
        <Icon className="h-3.5 w-3.5 shrink-0 text-agent" />
        <span className="min-w-0 flex-1 truncate text-[11px] text-zinc-300">{command.label}</span>
        <button
          onClick={onRun}
          className="flex h-6 shrink-0 items-center gap-1 rounded bg-agent px-2 text-[10px] font-semibold text-[#06211f] hover:bg-[#5eead4] transition-colors"
        >
          <Play className="h-2.5 w-2.5" />
          Run
        </button>
      </div>
    );
  }
  return (
    <div className="rounded border border-line bg-[#1a1917] p-3">
      <div className="flex items-start gap-2.5">
        <div className="grid h-7 w-7 shrink-0 place-items-center rounded bg-agent/10 text-agent">
          <Icon className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-zinc-100">{command.label}</div>
          <div className="mt-0.5 truncate font-mono text-[10px] text-zinc-500">{command.command}</div>
          <p className="mt-1 text-[11px] leading-4 text-zinc-500">{command.intent}</p>
        </div>
      </div>
      <button
        onClick={onRun}
        className="mt-2.5 flex h-7 w-full items-center justify-center gap-1.5 rounded bg-agent text-xs font-semibold text-[#06211f] hover:bg-[#5eead4] transition-colors"
      >
        <Play className="h-3 w-3" />
        Run
      </button>
    </div>
  );
}

// ─── Workflow Strip ──────────────────────────────────────────────────────────
function WorkflowStrip({
  objective,
  setObjective,
  workflow,
  onRun,
  isRunning,
  activeView,
}: {
  objective: string;
  setObjective: (v: string) => void;
  workflow: WorkflowStep[];
  onRun: () => void;
  isRunning: boolean;
  activeView: WorkspaceView;
}) {
  const isDashboard = activeView === "dashboard";
  return (
    <section className={cx(
      "flex shrink-0 items-center gap-2 border-b border-line bg-[#191714] px-3",
      isDashboard ? "py-1.5 opacity-80" : "py-2"
    )}>
      {/* Objective input */}
      <div className="flex min-w-0 flex-1 items-center gap-2 rounded border border-line bg-[#0f0e0d] px-2.5 py-1.5">
        <Sparkles className="h-3.5 w-3.5 shrink-0 text-agent" />
        <input
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          className="min-w-0 flex-1 bg-transparent text-xs text-zinc-200 outline-none placeholder:text-zinc-600"
          placeholder="Current objective…"
        />
      </div>

      {/* Workflow steps inline */}
      {!isDashboard && (
        <div className="hidden shrink-0 items-center gap-1 xl:flex">
          {workflow.map((step, i) => (
            <div
              key={step.id}
              className={cx(
                "flex h-7 items-center gap-1 rounded border px-2 text-[10px] font-medium transition-colors",
                stateClass[step.state],
              )}
            >
              {step.state === "done" ? (
                <Check className="h-3 w-3" />
              ) : step.state === "running" ? (
                <Activity className="h-3 w-3 animate-pulse" />
              ) : (
                <Circle className="h-3 w-3" />
              )}
              <span>{step.label}</span>
              {i < workflow.length - 1 && <ChevronRight className="ml-0.5 h-2.5 w-2.5 text-zinc-600" />}
            </div>
          ))}
        </div>
      )}

      {/* Run button */}
      {!isDashboard && (
        <button
          onClick={onRun}
          disabled={isRunning}
          title="Demo cycle only — not a real verification. Use Full Safe Audit instead."
          className="flex h-8 shrink-0 items-center gap-1.5 rounded border border-honey/30 bg-honey/10 px-3 text-xs font-semibold text-honey disabled:cursor-not-allowed disabled:bg-line disabled:text-zinc-500 hover:bg-honey/20 transition-colors"
        >
          {isRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
          <span className="hidden sm:inline">Demo Cycle</span>
        </button>
      )}
    </section>
  );
}

// ─── Main Pane ───────────────────────────────────────────────────────────────
function MainPane({
  activeView,
  selectedFile,
  loadedFiles,
  commandRuns,
  backendOnline,
  previewPath,
  previewLines,
  previewError,
  previewLoading,
  previewStart,
  previewEnd,
  previewDurationMs,
  setPreviewStart,
  setPreviewEnd,
  onReadRange,
  onLoadRoot,
  onRunAudit,
  backendHealth,
  activeModel,
  healthRating,
  loadedFileIds,
  auditActiveStep,
  setActiveView,
  onRunCommand,
  messages,
  chatInput,
  setChatInput,
  submitChat,
  isRunning,
  chatEndRef,
  responseLength,
  setResponseLength,
  temperature,
  setTemperature,
  triggerQuickPrompt,
  setActiveModel,
  auditEvents,
  rangeContextChunks,
  onAddRangeToContext,
  onClearChat,
  onTestModel,
  modelTestRunning,
  qaSnapshot,
  qaSnapshotLoading,
  onRefreshSnapshot,
  selectedFiles,
  setSelectedFiles,
}: {
  activeView: WorkspaceView;
  selectedFile: FileItem;
  loadedFiles: FileItem[];
  commandRuns: CommandRun[];
  backendOnline: boolean | null;
  previewPath: string | null;
  previewLines: FileLine[];
  previewError: string | null;
  previewLoading: boolean;
  previewStart: number;
  previewEnd: number;
  previewDurationMs: number | null;
  setPreviewStart: (v: number) => void;
  setPreviewEnd: (v: number) => void;
  onReadRange: (start: number, end: number) => void;
  onLoadRoot: () => void;
  onRunAudit: () => void;
  backendHealth: BridgeHealth | null;
  activeModel: ModelKey;
  healthRating: HealthRating | null;
  loadedFileIds: string[];
  auditActiveStep: number;
  setActiveView: (view: WorkspaceView) => void;
  onRunCommand: (cmd: SafeCommand) => void;
  messages: ChatMessage[];
  chatInput: string;
  setChatInput: (v: string) => void;
  submitChat: (e?: FormEvent) => void;
  isRunning: boolean;
  chatEndRef: RefObject<HTMLDivElement>;
  responseLength: ResponseLength;
  setResponseLength: (v: ResponseLength) => void;
  temperature: number;
  setTemperature: (v: number) => void;
  triggerQuickPrompt: (promptText: string) => void;
  setActiveModel: (m: ModelKey) => void;
  auditEvents: AuditEvent[];
  rangeContextChunks: ChatContextChunk[];
  onAddRangeToContext: () => void;
  onClearChat: () => void;
  onTestModel: () => void;
  modelTestRunning: boolean;
  qaSnapshot: BridgeQASnapshot | null;
  qaSnapshotLoading: boolean;
  onRefreshSnapshot: () => void;
  selectedFiles: string[];
  setSelectedFiles: React.Dispatch<React.SetStateAction<string[]>>;
}) {
  switch (activeView) {
    case "dashboard":
      return (
        <DashboardPage
          backendOnline={backendOnline}
          backendHealth={backendHealth}
          activeModel={activeModel}
          healthRating={healthRating}
          commandRuns={commandRuns}
          contextCount={rangeContextChunks.length}
          onRunAudit={onRunAudit}
          auditActiveStep={auditActiveStep}
          onNavigate={setActiveView}
          onLoadRoot={onLoadRoot}
          onRunCommand={onRunCommand}
          qaSnapshot={qaSnapshot}
          qaSnapshotLoading={qaSnapshotLoading}
          onRefreshSnapshot={onRefreshSnapshot}
        />
      );
    case "agent":
      return (
        <CentralChatPage
          messages={messages}
          chatInput={chatInput}
          setChatInput={setChatInput}
          submitChat={submitChat}
          isRunning={isRunning}
          chatEndRef={chatEndRef}
          activeModel={activeModel}
          responseLength={responseLength}
          setResponseLength={setResponseLength}
          temperature={temperature}
          setTemperature={setTemperature}
          triggerQuickPrompt={triggerQuickPrompt}
          rangeContextChunks={rangeContextChunks}
          onClearChat={onClearChat}
          onTestModel={onTestModel}
          modelTestRunning={modelTestRunning}
          selectedFiles={selectedFiles}
          setSelectedFiles={setSelectedFiles}
        />
      );
    case "files":
      return (
        <div className="flex h-full">
          <div className="min-h-0 min-w-0 flex-1 overflow-hidden">
            <LiveFilePane
              backendOnline={backendOnline}
              previewPath={previewPath}
              previewLines={previewLines}
              previewError={previewError}
              previewLoading={previewLoading}
              previewStart={previewStart}
              previewEnd={previewEnd}
              previewDurationMs={previewDurationMs}
              setPreviewStart={setPreviewStart}
              setPreviewEnd={setPreviewEnd}
              onReadRange={onReadRange}
              onAddRangeToContext={onAddRangeToContext}
              rangeContextChunks={rangeContextChunks}
              onLoadRoot={onLoadRoot}
              onRunAudit={onRunAudit}
            />
          </div>
          <div className="hidden w-[280px] shrink-0 flex-col border-l border-line bg-[#0F172A] lg:flex">
            <div className="flex h-9 shrink-0 items-center border-b border-line px-3">
              <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">Agent State</span>
            </div>
            <div className="thin-scrollbar min-h-0 flex-1 space-y-2 overflow-auto p-3">
              <InfoBlock
                icon={Database}
                label="Chat Context"
                value={`${rangeContextChunks.length} range${rangeContextChunks.length === 1 ? "" : "s"}`}
                detail={rangeContextChunks.map((chunk) => chunk.label).join(", ") || "none added"}
              />
              <InfoBlock
                icon={ClipboardCheck}
                label="Last Check"
                value={commandRuns[0]?.label ?? "not run"}
                detail={commandRuns[0]?.output.split("\n")[0] ?? "run a safe command first"}
              />
              <div className="rounded border border-honey/30 bg-honey/6 p-2.5">
                <div className="flex items-center gap-1.5 text-[11px] font-semibold text-honey">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                  Guardrail
                </div>
                <p className="mt-1.5 text-[11px] leading-4 text-zinc-400">
                  No fake completion. Every done state needs context, command output, or explicit approval.
                </p>
              </div>
            </div>
          </div>
        </div>
      );
    case "audit":
      return (
        <AuditPage
          auditEvents={auditEvents}
          healthRating={healthRating}
          onRunAudit={onRunAudit}
          commandRuns={commandRuns}
          isRunning={isRunning}
          auditActiveStep={auditActiveStep}
        />
      );
    case "commands":
      return (
        <CommandsPage
          onRunCommand={onRunCommand}
          commandRuns={commandRuns}
          isRunning={isRunning}
        />
      );
    case "reports":
      return <ReportsPage />;
    case "safety":
      return <SafetyPage />;
    case "settings":
      return (
        <SettingsPage
          activeModel={activeModel}
          setActiveModel={setActiveModel}
          responseLength={responseLength}
          setResponseLength={setResponseLength}
          temperature={temperature}
          setTemperature={setTemperature}
          onTestModel={onTestModel}
          modelTestRunning={modelTestRunning}
          backendOnline={backendOnline}
        />
      );
    default:
      return <CodePane file={selectedFile} />;
  }
}

// ─── Sub Pages for AGENT ALINE X Web v2.4 ───────────────────────────────────

function DashboardPage({
  backendOnline,
  backendHealth,
  activeModel,
  healthRating,
  commandRuns,
  contextCount,
  onRunAudit,
  auditActiveStep,
  onNavigate,
  onLoadRoot,
  onRunCommand,
  qaSnapshot,
  qaSnapshotLoading,
  onRefreshSnapshot,
}: {
  backendOnline: boolean | null;
  backendHealth: BridgeHealth | null;
  activeModel: ModelKey;
  healthRating: HealthRating | null;
  commandRuns: CommandRun[];
  contextCount: number;
  onRunAudit: () => void;
  auditActiveStep: number;
  onNavigate: (view: WorkspaceView) => void;
  onLoadRoot: () => void;
  onRunCommand: (cmd: SafeCommand) => void;
  qaSnapshot: BridgeQASnapshot | null;
  qaSnapshotLoading: boolean;
  onRefreshSnapshot: () => void;
}) {
  const auditSteps = [
    { id: "git-status", label: "Git Status" },
    { id: "git-diff-stat", label: "Git Diff Stat" },
    { id: "git-log-short", label: "Git Log" },
    { id: "python-compile", label: "Python Compile" },
    { id: "frontend-build", label: "Frontend Build" },
    { id: "backend-health", label: "Backend Health" },
  ];

  const latestAuditRuns = auditSteps.map(step => commandRuns.find(run => run.commandId === step.id));
  const passCount = latestAuditRuns.filter(run => run && run.exitCode === 0).length;
  const failCount = latestAuditRuns.filter(run => run && run.exitCode !== 0).length;
  const pendingCount = 6 - passCount - failCount;

  return (
    <div className="thin-scrollbar h-full overflow-auto bg-shell p-6 text-zinc-100">
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-agent to-iris">
          AGENT ALINE X
        </h1>
        <p className="mt-1.5 text-sm text-zinc-400">Local AI Agent Workbench</p>
        <p className="mt-1 text-[11px] text-zinc-500">
          <span className="font-semibold text-zinc-400">v3.1</span> · Release Candidate · P7 Final QA ·
          Tests: <code className="text-zinc-400">py -3.11 -m pytest -q</code> ·
          Build: <code className="text-zinc-400">npm.cmd run build</code>
        </p>
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="premium-card p-4">
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>BACKEND BRIDGE</span>
            <Radio className={cx("h-4 w-4", backendOnline ? "text-mint animate-pulse" : "text-tomato")} />
          </div>
          <div className="mt-2 text-lg font-bold">
            {backendOnline === null ? "Checking..." : backendOnline ? "Online" : "Offline"}
          </div>
          <div className="mt-1 text-[11px] text-zinc-500">http://127.0.0.1:8787</div>
        </div>

        <div className="premium-card p-4">
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>OLLAMA STATUS</span>
            <Check className={cx("h-4 w-4", backendOnline && backendHealth?.ollama === "ok" ? "text-mint" : "text-tomato")} />
          </div>
          <div className="mt-2 text-lg font-bold">
            {backendOnline && backendHealth?.ollama === "ok" ? "Running OK" : "Offline / Error"}
          </div>
          <div className="mt-1 text-[11px] text-zinc-500">Ollama API port 11434</div>
        </div>

        <div className="premium-card p-4">
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>ACTIVE MODEL</span>
            <Bot className="h-4 w-4 text-iris" />
          </div>
          <div className="mt-2 text-xs font-bold truncate" title={activeModel}>
            {activeModel}
          </div>
          <div className="mt-1.5 text-[10px] uppercase tracking-wider text-iris font-semibold">Local LLM</div>
        </div>

        <div className="premium-card p-4 border border-honey/20">
          <div className="flex items-center justify-between text-xs text-zinc-500">
            <span>PATCH MODE</span>
            <Lock className="h-4 w-4 text-honey" />
          </div>
          <div className="mt-2 text-lg font-bold text-honey">OFF</div>
          <div className="mt-1 text-[11px] text-zinc-500">Safe read-only execution</div>
        </div>
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Primary CTA */}
        <button
          onClick={onRunAudit}
          disabled={auditActiveStep > 0 && auditActiveStep < 7}
          className="flex h-16 items-center justify-between rounded-xl bg-gradient-to-r from-agent to-[#0e7490] text-[#042f2e] border-none p-4 hover:from-[#5eead4] hover:to-[#0891b2] text-left transition-all shadow-[0_0_20px_rgba(34,211,238,0.2)] hover:shadow-[0_0_25px_rgba(34,211,238,0.35)] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="min-w-0">
            <div className="text-sm font-black tracking-wide uppercase">Start Full Safe Audit</div>
            <div className="truncate text-[11px] text-[#042f2e]/80 font-semibold mt-0.5">Run code, compilation & health checks</div>
          </div>
          <ShieldCheck className="h-6 w-6 shrink-0 text-[#042f2e]" />
        </button>

        {/* Secondary CTA: Open Workspace */}
        <button
          onClick={() => onNavigate("files")}
          className="flex h-16 items-center justify-between rounded-xl bg-[#1e293b]/20 border border-line p-4 hover:border-iris hover:bg-[#1e293b]/45 text-left transition-all"
        >
          <div className="min-w-0">
            <div className="text-sm font-bold text-zinc-200">Open Workspace</div>
            <div className="truncate text-xs text-zinc-500 mt-0.5">Inspect project code & file range preview</div>
          </div>
          <Files className="h-5 w-5 shrink-0 text-iris" />
        </button>

        {/* Secondary CTA: Ask Agent */}
        <button
          onClick={() => onNavigate("agent")}
          className="flex h-16 items-center justify-between rounded-xl bg-[#1e293b]/20 border border-line p-4 hover:border-mint hover:bg-[#1e293b]/45 text-left transition-all"
        >
          <div className="min-w-0">
            <div className="text-sm font-bold text-zinc-200">Ask Agent</div>
            <div className="truncate text-xs text-zinc-500 mt-0.5">Chat with grounded file context</div>
          </div>
          <Send className="h-5 w-5 shrink-0 text-mint" />
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 items-start">
        <div className="premium-card p-5">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <h3 className="text-xs font-bold tracking-wide text-zinc-300">ONE-CLICK SAFE AUDIT</h3>
            {healthRating && (
              <span className={cx(
                "rounded px-2 py-0.5 text-[10px] font-bold uppercase",
                healthRating === "Healthy" && "bg-mint/15 text-mint",
                healthRating === "Needs Attention" && "bg-honey/15 text-honey",
                healthRating === "Critical" && "bg-tomato/15 text-tomato",
              )}>
                {healthRating}
              </span>
            )}
          </div>

          <div className="mt-4 space-y-3.5">
            {auditSteps.map((step, idx) => {
              const stepNum = idx + 1;
              const run = latestAuditRuns[idx];
              const isCurrent = auditActiveStep === stepNum;
              const isPast = auditActiveStep > stepNum || auditActiveStep === 7;
              const isFailed = run && run.exitCode !== 0;

              return (
                <div key={step.id} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className={cx(
                      "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold border",
                      isCurrent && "border-agent bg-agent/10 text-agent animate-pulse",
                      isPast && !isFailed && "border-mint bg-mint/15 text-mint",
                      isPast && isFailed && "border-tomato bg-tomato/15 text-tomato",
                      !isCurrent && !isPast && "border-line text-zinc-500",
                    )}>
                      {isPast ? (isFailed ? "✕" : "✓") : stepNum}
                    </div>
                    <span className={cx(
                      isCurrent && "font-semibold text-agent",
                      isPast && "text-zinc-200",
                      !isCurrent && !isPast && "text-zinc-500",
                    )}>{step.label}</span>
                  </div>
                  <div className="text-[10px] text-zinc-500">
                    {isCurrent && "auditing..."}
                    {isPast && (run ? `${run.duration} · exit ${run.exitCode}` : "done")}
                    {!isCurrent && !isPast && "queued"}
                  </div>
                </div>
              );
            })}
          </div>

          {commandRuns.length > 0 && (
            <div className="mt-5 rounded border border-line bg-panel2 p-3">
              <div className="flex items-center justify-between text-[11px] text-zinc-400">
                <span>Pass: <span className="font-semibold text-mint">{passCount}</span></span>
                <span>Fail: <span className="font-semibold text-tomato">{failCount}</span></span>
                <span>Pending: <span className="font-semibold text-zinc-500">{pendingCount}</span></span>
              </div>
              <button
                onClick={() => onNavigate("audit")}
                className="mt-3 text-xs font-semibold text-agent hover:underline flex items-center gap-1"
              >
                Open Audit Details <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="premium-card p-5">
            <h3 className="mb-3 text-xs font-bold tracking-wide text-zinc-300">RECENT WORKBENCH STATUS</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-zinc-500">Last Command Run:</span>
                <span className="font-medium text-zinc-300">{commandRuns[0]?.label || "None"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Live chat context:</span>
                <span className="font-medium text-iris">{contextCount} ranges</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Local Security Health:</span>
                <span className="font-medium text-zinc-400">{"Run Full Safe Audit to check"}</span>
              </div>
            </div>
          </div>

          <div className="premium-card p-5">
            <h3 className="mb-4 text-xs font-bold tracking-wide text-zinc-300">QUICK ACTIONS</h3>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => onRunCommand(safeCommands.find(c => c.id === "git-status")!)}
                className="flex h-9 items-center justify-center gap-1.5 rounded border border-line bg-panel hover:bg-panel2 text-xs text-zinc-300 transition-colors"
              >
                <GitBranch className="h-3.5 w-3.5 text-agent" />
                Git Status
              </button>
              <button
                onClick={() => onRunCommand(safeCommands.find(c => c.id === "frontend-build")!)}
                className="flex h-9 items-center justify-center gap-1.5 rounded border border-line bg-panel hover:bg-panel2 text-xs text-zinc-300 transition-colors"
              >
                <Hammer className="h-3.5 w-3.5 text-iris" />
                Frontend Build
              </button>
              <button
                onClick={onLoadRoot}
                className="flex h-9 items-center justify-center gap-1.5 rounded border border-line bg-panel hover:bg-panel2 text-xs text-zinc-300 transition-colors col-span-2"
              >
                <Folder className="h-3.5 w-3.5 text-honey" />
                Open AGENT_ALINE_X root
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-honey/20 bg-honey/5 p-4">
            <div className="flex items-center gap-2 text-xs font-bold text-honey">
              <Lock className="h-4 w-4" />
              BENCHMARK SECURITY GUARANTEES
            </div>
            <ul className="mt-2 space-y-1 text-[11px] leading-4 text-zinc-400 list-disc list-inside">
              <li>No free terminal command execution (only predefined safe command scripts).</li>
              <li>Credential blocking protects keys, certs, and `.env` files automatically.</li>
              <li>OCR codebase is mapped read-only to prevent destructive overwrite mistakes.</li>
            </ul>
          </div>
        </div>
      </div>

      {/* ── System QA Snapshot card ─────────────────────────────────── */}
      <div className="mt-6 premium-card p-5">
        <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-agent" />
            <h3 className="text-xs font-bold uppercase tracking-wide text-zinc-300">System QA Snapshot</h3>
            {qaSnapshot && (
              <span className={cx(
                "rounded px-2 py-0.5 text-[10px] font-bold uppercase",
                qaSnapshot.overall_status === "Healthy" ? "bg-mint/15 text-mint" : "bg-honey/15 text-honey",
              )}>
                {qaSnapshot.overall_status}
              </span>
            )}
          </div>
          <button
            onClick={onRefreshSnapshot}
            disabled={qaSnapshotLoading}
            className="flex h-7 items-center gap-1.5 rounded border border-agent/30 bg-agent/8 px-3 text-xs font-semibold text-agent hover:bg-agent/20 disabled:cursor-not-allowed disabled:text-zinc-600 transition-colors"
          >
            {qaSnapshotLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            {qaSnapshotLoading ? "Fetching…" : "Refresh Snapshot"}
          </button>
        </div>

        {!qaSnapshot && !qaSnapshotLoading && (
          <p className="text-xs text-zinc-500 italic">Click 'Refresh Snapshot' to load live backend QA data.</p>
        )}
        {qaSnapshotLoading && (
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-agent" />
            Loading snapshot from backend…
          </div>
        )}
        {qaSnapshot && !qaSnapshotLoading && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded border border-line bg-panel2 p-3">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Backend</div>
              <div className={cx("text-sm font-bold", qaSnapshot.backend_ok ? "text-mint" : "text-tomato")}>
                {qaSnapshot.backend_ok ? "✅ OK" : "❌ Error"}
              </div>
            </div>
            <div className="rounded border border-line bg-panel2 p-3">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Ollama</div>
              <div className={cx("text-sm font-bold", qaSnapshot.ollama_status === "ok" ? "text-mint" : "text-tomato")}>
                {qaSnapshot.ollama_status === "ok" ? "✅ ok" : "❌ error"}
              </div>
            </div>
            <div className="rounded border border-line bg-panel2 p-3">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Active Model</div>
              <div className="text-xs font-bold text-iris truncate" title={qaSnapshot.active_model}>{qaSnapshot.active_model}</div>
            </div>
            <div className="rounded border border-line bg-panel2 p-3">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Patch Mode</div>
              <div className="text-sm font-bold text-honey">{qaSnapshot.patch_mode.toUpperCase()}</div>
            </div>
            <div className="rounded border border-line bg-panel2 p-3">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Safe Commands</div>
              <div className="text-sm font-bold text-zinc-200">{qaSnapshot.safe_command_count}</div>
            </div>
            <div className="rounded border border-line bg-panel2 p-3">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Timeout Budgets</div>
              <div className="text-xs text-zinc-300">
                Quick {qaSnapshot.quick_timeout}s · Bal {qaSnapshot.balanced_timeout}s · Det {qaSnapshot.detailed_timeout}s
              </div>
            </div>
            <div className="rounded border border-line bg-panel2 p-3 sm:col-span-2 lg:col-span-3">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-1">Last Checked</div>
              <div className="font-mono text-xs text-zinc-400">{new Date(qaSnapshot.timestamp).toLocaleString()}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CentralChatPage({
  messages,
  chatInput,
  setChatInput,
  submitChat,
  isRunning,
  chatEndRef,
  activeModel,
  responseLength,
  setResponseLength,
  temperature,
  setTemperature,
  triggerQuickPrompt,
  rangeContextChunks,
  onClearChat,
  onTestModel,
  modelTestRunning,
  selectedFiles,
  setSelectedFiles,
}: {
  messages: ChatMessage[];
  chatInput: string;
  setChatInput: (v: string) => void;
  submitChat: (e?: FormEvent) => void;
  isRunning: boolean;
  chatEndRef: RefObject<HTMLDivElement>;
  activeModel: ModelKey;
  responseLength: ResponseLength;
  setResponseLength: (v: ResponseLength) => void;
  temperature: number;
  setTemperature: (v: number) => void;
  triggerQuickPrompt: (promptText: string) => void;
  rangeContextChunks: ChatContextChunk[];
  onClearChat: () => void;
  onTestModel: () => void;
  modelTestRunning: boolean;
  selectedFiles: string[];
  setSelectedFiles: React.Dispatch<React.SetStateAction<string[]>>;
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ProjectSearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  const handleSearch = () => {
    const q = searchQuery.trim();
    if (!q) return;
    setSearchLoading(true);
    searchProject(q).then((res) => {
      setSearchLoading(false);
      if (res && res.results) {
        setSearchResults(res.results);
      } else {
        setSearchResults([]);
      }
    });
  };
  const quickPrompts = ["Hi", "Explain project", "Run Safe Audit", "Check risks", "Generate Daily Report"];
  const latestAgentText = [...messages].reverse().find((msg) => msg.role === "agent")?.text ?? "";
  const latestMemoryChunks = [...messages].reverse().find((msg) => msg.role === "agent" && (msg.memoryContextChunks ?? 0) > 0)?.memoryContextChunks ?? 0;
  const visibleContextCount = Math.max(rangeContextChunks.length, latestMemoryChunks, selectedFiles.length);
  const followUps = latestAgentText.includes("Run Quick Audit") || latestAgentText.includes("Not checked")
    ? ["Run Safe Audit"]
    : latestAgentText.toLowerCase().includes("ready")
      ? ["Run Safe Audit", "Explain project"]
      : [];

  return (
    <div className="flex h-full flex-col bg-shell text-zinc-100">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-panel px-4">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-iris" />
          <span className="text-sm font-semibold">Central Agent Chat</span>
        </div>
        <div className="flex min-w-0 items-center gap-2">
          <div className="hidden items-center gap-1.5 rounded border border-line bg-panel2 px-2 py-0.5 text-[11px] text-zinc-400 sm:flex">
            <Database className="h-3.5 w-3.5 text-agent" />
            {visibleContextCount} context
          </div>
          <div className="flex min-w-0 items-center gap-1.5 rounded border border-iris/20 bg-iris/10 px-2.5 py-0.5 font-mono text-xs text-iris">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-mint animate-pulse" />
            <span className="max-w-[180px] truncate">{activeModel === "auto" ? "Auto Router" : activeModel}</span>
          </div>
          <button
            type="button"
            onClick={onTestModel}
            disabled={modelTestRunning}
            className="grid h-7 w-7 place-items-center rounded border border-line text-zinc-500 hover:border-agent/50 hover:text-agent disabled:cursor-not-allowed"
            title="Test active model"
          >
            {modelTestRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <TestTube2 className="h-3.5 w-3.5" />}
          </button>
          <button
            type="button"
            onClick={onClearChat}
            className="grid h-7 w-7 place-items-center rounded border border-line text-zinc-500 hover:border-tomato/50 hover:text-tomato"
            title="Clear chat"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="shrink-0 bg-panel px-4 py-2 border-b border-line flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleSearch();
                }
              }}
              placeholder="Search project files to attach context..."
              className="w-full bg-shell border border-line rounded-lg py-1.5 pl-8 pr-3 text-xs text-zinc-200 outline-none focus:border-agent/50"
            />
          </div>
          <button
            type="button"
            onClick={handleSearch}
            disabled={searchLoading}
            className="rounded border border-line hover:border-agent bg-panel2 px-3 py-1.5 text-xs text-zinc-300 disabled:opacity-50"
          >
            {searchLoading ? "Searching..." : "Search"}
          </button>
          {searchResults.length > 0 && (
            <button
              type="button"
              onClick={() => { setSearchResults([]); setSearchQuery(""); }}
              className="text-xs text-zinc-500 hover:text-zinc-300"
            >
              Clear
            </button>
          )}
        </div>
        
        {searchResults.length > 0 && (
          <div className="thin-scrollbar max-h-36 overflow-y-auto rounded border border-line bg-[#0f0e0d] p-2 space-y-1.5">
            {searchResults.map((res) => {
              const isAdded = selectedFiles.includes(res.relative_path);
              return (
                <div key={res.relative_path} className="flex items-center justify-between gap-4 text-xs hover:bg-panel p-1 rounded">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-zinc-300 truncate" title={res.relative_path}>{res.file_name}</span>
                      <span className="text-[10px] text-zinc-500 truncate">{res.relative_path}</span>
                    </div>
                    {res.snippet && (
                      <pre className="mt-1 max-h-12 overflow-hidden text-[9px] text-zinc-400 font-mono bg-shell p-1 rounded whitespace-pre-wrap select-all">
                        {res.snippet}
                      </pre>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      if (isAdded) {
                        setSelectedFiles(prev => prev.filter(f => f !== res.relative_path));
                      } else {
                        setSelectedFiles(prev => [...prev, res.relative_path]);
                      }
                    }}
                    className={cx(
                      "shrink-0 rounded px-2 py-1 text-[10px] font-bold transition-all",
                      isAdded 
                        ? "bg-tomato/15 text-tomato border border-tomato/30 hover:bg-tomato/25" 
                        : "bg-agent/15 text-agent border border-agent/30 hover:bg-agent/25"
                    )}
                  >
                    {isAdded ? "Remove" : "Add Context"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="thin-scrollbar min-h-0 flex-1 overflow-auto p-6 space-y-4">
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          const isSys = msg.role === "system";
          return (
            <div
              key={msg.id}
              className={cx(
                "flex flex-col max-w-[80%] rounded-xl border p-4 shadow-sm transition-all",
                isUser
                  ? "ml-auto bg-panel2 border-agent/20 text-zinc-200"
                  : isSys
                    ? "mx-auto border-honey/20 bg-honey/5 text-honey max-w-[90%] text-center text-xs"
                    : "mr-auto bg-panel border-line text-zinc-200",
              )}
            >
              <div className="mb-1 flex items-center justify-between text-[10px] uppercase tracking-wider text-zinc-500 font-semibold border-b border-line/45 pb-1">
                <span>{isUser ? "You" : isSys ? "System Action" : "Agent aline x"}</span>
                <div className="flex items-center gap-2">
                  {!isUser && !isSys && (
                    <button
                      type="button"
                      onClick={() => navigator.clipboard.writeText(msg.text)}
                      className="flex items-center gap-1 rounded border border-line px-1.5 py-0.5 text-[10px] text-zinc-500 hover:border-agent/50 hover:text-agent"
                      title="Copy response"
                    >
                      <Copy className="h-3 w-3" />
                      Copy
                    </button>
                  )}
                  <ChatMetaBadges msg={msg} />
                  <span>{msg.time}</span>
                </div>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-6 mt-1.5">{msg.text}</p>
            </div>
          );
        })}
        {isRunning && (
          <div className="mr-auto flex items-center gap-2 rounded-xl border border-line bg-panel px-4 py-3 text-zinc-400">
            <Loader2 className="h-4 w-4 animate-spin text-iris" />
            <span className="text-xs">Thinking...</span>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {followUps.length > 0 && (
        <div className="shrink-0 border-t border-line/40 bg-shell px-6 py-2">
          <div className="mx-auto flex max-w-4xl flex-wrap justify-center gap-1.5">
            {followUps.map((prompt) => (
              <button
                key={prompt}
                onClick={() => triggerQuickPrompt(prompt)}
                className="rounded border border-agent/30 bg-agent/10 px-3 py-1 text-xs font-medium text-agent hover:bg-agent/15"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="shrink-0 bg-shell px-6 py-2 border-t border-line/40 flex flex-wrap gap-1.5 justify-center">
        {quickPrompts.map((prompt) => (
          <button
            key={prompt}
            onClick={() => triggerQuickPrompt(prompt)}
            className="rounded-full border border-line bg-panel px-3 py-1 text-xs text-zinc-400 hover:border-agent/50 hover:text-agent hover:bg-panel2 transition-all"
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="shrink-0 border-t border-line bg-[#0E1528] p-4">
        {selectedFiles.length > 0 && (
          <div className="mx-auto max-w-4xl flex flex-wrap gap-1.5 items-center p-2 rounded border border-line bg-panel2 mb-2">
            <span className="text-[10px] uppercase font-bold text-zinc-500 mr-1.5">Attached Files ({selectedFiles.length}):</span>
            {selectedFiles.map((file) => (
              <span key={file} className="inline-flex items-center gap-1 rounded bg-[#0f0e0d] border border-line px-2 py-0.5 text-xs text-zinc-300">
                <span className="truncate max-w-[150px]" title={file}>{file.split('/').pop()}</span>
                <button type="button" onClick={() => setSelectedFiles(prev => prev.filter(f => f !== file))} className="text-zinc-500 hover:text-tomato">
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
            <button
              type="button"
              onClick={() => setSelectedFiles([])}
              className="text-[10px] text-tomato hover:underline ml-auto"
            >
              Clear All
            </button>
          </div>
        )}
        <form onSubmit={submitChat} className="mx-auto max-w-4xl flex items-end gap-3 rounded-xl border border-line bg-panel px-4 py-3 focus-within:border-agent/50 transition-colors">
          <textarea
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submitChat();
              }
            }}
            rows={2}
            className="thin-scrollbar min-h-[44px] w-full resize-none bg-transparent text-sm text-zinc-200 outline-none placeholder:text-zinc-600"
            placeholder="Ask the agent... (Enter to send, Shift+Enter for newline)"
          />
          <button
            type="submit"
            disabled={!chatInput.trim() || isRunning}
            className="flex h-9 shrink-0 items-center gap-1.5 rounded-lg bg-agent px-4 text-xs font-bold text-[#06211f] disabled:cursor-not-allowed disabled:bg-line disabled:text-zinc-500 hover:bg-[#5eead4] transition-colors"
          >
            <Send className="h-3.5 w-3.5" />
            Send
          </button>
        </form>

        <div className="mt-2 mx-auto max-w-4xl flex flex-wrap justify-between items-center text-[11px] text-zinc-500 px-1 gap-2">
          <div className="flex items-center gap-2">
            <span>Response Length:</span>
            <div className="flex rounded border border-line overflow-hidden">
              {(["Quick", "Balanced", "Detailed"] as ResponseLength[]).map((rl) => (
                <button
                  type="button"
                  key={rl}
                  onClick={() => setResponseLength(rl)}
                  className={cx(
                    "px-2 py-0.5 border-r border-line last:border-0 hover:bg-panel hover:text-zinc-300",
                    responseLength === rl && "bg-agent/15 text-agent font-semibold",
                  )}
                >
                  {rl}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span>Temp:</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
              className="w-24 accent-agent cursor-pointer"
            />
            <span className="font-mono text-zinc-300">{temperature.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function AuditPage({
  auditEvents,
  healthRating,
  onRunAudit,
  commandRuns,
  isRunning,
  auditActiveStep,
}: {
  auditEvents: AuditEvent[];
  healthRating: HealthRating | null;
  onRunAudit: () => void;
  commandRuns: CommandRun[];
  isRunning: boolean;
  auditActiveStep: number;
}) {
  const auditSteps = [
    { id: "git-status", label: "Git Status" },
    { id: "git-diff-stat", label: "Git Diff Stat" },
    { id: "git-log-short", label: "Git Log" },
    { id: "python-compile", label: "Python Compile" },
    { id: "frontend-build", label: "Frontend Build" },
    { id: "backend-health", label: "Backend Health" },
  ];

  return (
    <div className="thin-scrollbar h-full overflow-auto bg-shell p-6 text-zinc-100">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-zinc-200">Audit Dashboard</h2>
          <p className="text-xs text-zinc-400 mt-1">Review validation results and check system boundaries</p>
        </div>
        <button
          onClick={onRunAudit}
          disabled={isRunning}
          className="flex h-9 items-center justify-center gap-2 rounded bg-agent px-4 text-sm font-semibold text-[#06211f] disabled:cursor-not-allowed disabled:bg-line disabled:text-zinc-500 hover:bg-[#5eead4] transition-colors"
        >
          {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
          Run Full Safe Audit
        </button>
      </div>

      {healthRating && (
        <div className={cx(
          "mb-6 rounded-xl border p-4 flex items-center justify-between",
          healthRating === "Healthy" && "border-mint/30 bg-mint/5 text-mint",
          healthRating === "Needs Attention" && "border-honey/30 bg-honey/5 text-honey",
          healthRating === "Critical" && "border-tomato/30 bg-tomato/5 text-tomato",
        )}>
          <div>
            <div className="text-xs uppercase tracking-wider text-zinc-500">Global Security Health Rating</div>
            <div className="text-2xl font-bold mt-1">{healthRating}</div>
          </div>
          <div className="text-xs text-right text-zinc-400">
            All strict local rules are currently ACTIVE
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Audit Commands Results</h3>
          {auditSteps.map((step) => {
            const run = commandRuns.find(r => r.commandId === step.id);
            const passed = run && run.exitCode === 0;
            return (
              <div key={step.id} className="premium-card p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-zinc-200">{step.label}</span>
                  {run ? (
                    <span className={cx(
                      "rounded px-2 py-0.5 text-[10px] font-bold uppercase",
                      passed ? "bg-mint/15 text-mint" : "bg-tomato/15 text-tomato",
                    )}>
                      {passed ? "PASS" : `FAIL (${run.exitCode})`}
                    </span>
                  ) : (
                    <span className="text-zinc-500 text-xs">NOT AUDITED</span>
                  )}
                </div>
                {run && (
                  <div className="mt-2.5">
                    <div className="flex justify-between text-[10px] text-zinc-500">
                      <span>Duration: {run.duration}</span>
                      <span>Run time: {run.time}</span>
                    </div>
                    <pre className="mt-2 max-h-24 overflow-y-auto thin-scrollbar rounded bg-shell p-2.5 font-mono text-[10px] leading-4 text-zinc-400 whitespace-pre-wrap select-all">
                      {run.output}
                    </pre>
                    {/* Failure analysis — only for failed steps */}
                    {run.exitCode !== 0 && run.failureAnalysis && (
                      <FailureAnalysisCard fa={run.failureAnalysis} />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="premium-card p-5 h-fit">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 border-b border-line pb-2 mb-4">Detailed Timeline</h3>
          <div className="space-y-3 max-h-[420px] overflow-y-auto thin-scrollbar pr-1">
            {auditEvents.length === 0 ? (
              <div className="text-center py-6 text-xs text-zinc-500">No events logged. Run the safe audit.</div>
            ) : (
              auditEvents.map((ev) => (
                <div key={ev.id} className="text-xs border-l-2 border-line pl-3 py-0.5">
                  <div className="flex items-center justify-between text-[10px] text-zinc-500 font-semibold">
                    <span>{ev.label}</span>
                    <span>{ev.time}</span>
                  </div>
                  <p className="mt-1 text-zinc-300">{ev.detail}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Failure Analysis Card ───────────────────────────────────────────────────
function FailureAnalysisCard({ fa }: { fa: FailureAnalysis }) {
  return (
    <div className="mt-3 rounded-lg border border-tomato/30 bg-tomato/5 p-3 space-y-2">
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-tomato">
        <AlertTriangle className="h-3 w-3 shrink-0" />
        Failure Analysis
      </div>
      <div className="grid grid-cols-1 gap-1.5 text-[11px]">
        <div className="flex flex-col gap-0.5">
          <span className="font-semibold text-zinc-400">Root Cause</span>
          <span className="text-zinc-200 leading-4">{fa.root_cause}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="font-semibold text-zinc-400">Likely File</span>
          <span className="font-mono text-honey break-all">{fa.likely_file}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="font-semibold text-zinc-400">Safe Fix Direction</span>
          <span className="text-zinc-200 leading-4">{fa.safe_fix_direction}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="font-semibold text-zinc-400">Next Test Command</span>
          <code className="rounded bg-shell/80 border border-line px-1.5 py-0.5 font-mono text-[10px] text-agent break-all">{fa.next_test_command}</code>
        </div>
      </div>
    </div>
  );
}

function CommandsPage({
  onRunCommand,
  commandRuns,
  isRunning,
}: {
  onRunCommand: (cmd: SafeCommand) => void;
  commandRuns: CommandRun[];
  isRunning: boolean;
}) {
  const activeRun = commandRuns[0];

  return (
    <div className="thin-scrollbar h-full overflow-auto bg-shell p-6 text-zinc-100">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-zinc-200">Safe Commands Board</h2>
        <p className="text-xs text-zinc-400 mt-1">Pre-approved scripts to query status without root modifications</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-3.5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Available Scripts</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {safeCommands.map((cmd) => {
              const Icon = cmd.icon;
              return (
                <div key={cmd.id} className="premium-card p-4 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 text-zinc-200 font-semibold text-sm">
                      <Icon className="h-4 w-4 text-agent" />
                      {cmd.label}
                    </div>
                    <code className="mt-2 block bg-shell/80 border border-line px-1.5 py-0.5 rounded font-mono text-[10px] text-zinc-500 truncate" title={cmd.command}>
                      {cmd.command}
                    </code>
                    <p className="mt-2 text-xs leading-4 text-zinc-400">{cmd.intent}</p>
                  </div>
                  <button
                    disabled={isRunning}
                    onClick={() => onRunCommand(cmd)}
                    className="mt-4 flex h-8 w-full items-center justify-center gap-1 rounded bg-agent text-xs font-semibold text-[#06211f] disabled:cursor-not-allowed disabled:bg-line disabled:text-zinc-500 hover:bg-[#5eead4] transition-colors"
                  >
                    <Play className="h-3 w-3" />
                    Run Command
                  </button>
                  {/* Failure analysis for most recent run of this command */}
                  {(() => {
                    const lastRun = commandRuns.find(r => r.commandId === cmd.id);
                    if (!lastRun || lastRun.exitCode === 0 || !lastRun.failureAnalysis) return null;
                    return <FailureAnalysisCard fa={lastRun.failureAnalysis} />;
                  })()}
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex h-[500px] flex-col overflow-hidden rounded-xl border border-line bg-panel shadow-lg">
          <div className="flex items-center justify-between bg-panel border-b border-line px-3 py-2 text-[11px] text-zinc-400 font-semibold font-mono">
            <span className="flex items-center gap-1.5">
              <SquareTerminal className="h-3.5 w-3.5 text-agent" />
              Latest Safe Output
            </span>
            {activeRun && (
              <span className={activeRun.exitCode === 0 ? "text-mint animate-pulse" : "text-tomato animate-pulse"}>
                exit {activeRun.exitCode}
              </span>
            )}
          </div>
          <div className="flex-1 p-3 font-mono text-[11px] leading-5 text-zinc-400 overflow-y-auto thin-scrollbar whitespace-pre-wrap select-all">
            {activeRun ? (
              <div>
                <span className="text-zinc-500">[{activeRun.time}] {activeRun.label} ({activeRun.duration})</span>
                <div className="mt-2 text-zinc-200">{activeRun.output}</div>
              </div>
            ) : (
              <div className="text-zinc-600 italic">No output yet. Click any command trigger to run.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ReportsPage() {
  const [selectedTemplate, setSelectedTemplate] = useState(reportTemplates[0]);
  const [copied, setCopied] = useState(false);
  const [qaReportLoading, setQaReportLoading] = useState(false);
  const [qaReportText, setQaReportText] = useState<string | null>(null);
  const [qaReportCopied, setQaReportCopied] = useState(false);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExport = (text: string, filename?: string) => {
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename ?? `agent-aline-x-${selectedTemplate.label.toLowerCase().replace(/\s+/g, "-")}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const handleExportQAReport = () => {
    if (qaReportLoading) return;
    setQaReportLoading(true);
    setQaReportText(null);
    fetchQAReport().then((data) => {
      setQaReportLoading(false);
      if (!data) {
        setQaReportText("⚠️ Backend bridge offline. Start RUN_WEB_V2.ps1 and try again.");
        return;
      }
      setQaReportText(data.report);
      handleExport(data.report, `agent-aline-x-qa-report-${new Date().toISOString().slice(0, 10)}.md`);
    });
  };

  const handleCopyQAReport = () => {
    if (!qaReportText) return;
    navigator.clipboard.writeText(qaReportText);
    setQaReportCopied(true);
    setTimeout(() => setQaReportCopied(false), 2000);
  };

  const getTemplateContent = (label: string) => {
    if (label.includes("Daily")) {
      return `### DAILY STATUS REPORT - AGENT ALINE X\n\n**Date**: ${new Date().toLocaleDateString()}\n**Objective**: Not checked yet.\n\n#### 1. Completed\n- Not checked yet. Run Quick Audit first.\n\n#### 2. Risks\n- Not checked yet.\n\n#### 3. Verification\n- Backend compile: Not checked.\n- Frontend build: Not checked.\n\n#### 4. Next Step\nRun Full Safe Audit and update this report from verified output.`;
    }
    if (label.includes("Bug")) {
      return `### BUG INVESTIGATION - AGENT ALINE X\n\n**Issue**: Not checked yet.\n\n#### Repro\n- Not checked yet.\n\n#### Evidence\n- Not checked yet.\n\n#### Likely Cause\n- Not checked yet.\n\n#### Safe Next Step\nRun the smallest relevant safe command or read the owning file range.`;
    }
    if (label.includes("Failure")) {
      return `### TEST FAILURE SUMMARY - AGENT ALINE X\n\n**Failing Check**: Not checked yet.\n\n#### Output\n- Not checked yet.\n\n#### Suspected Cause\n- Not checked yet.\n\n#### Retest Plan\nRun the failing command again after the fix and record exact output.`;
    }
    return `### RELEASE READINESS AUDIT - AGENT ALINE X\n\n**Status**: Not checked yet.\n\n#### Checklist\n- [ ] Backend compile verified\n- [ ] Frontend build verified\n- [ ] Health endpoint verified\n- [ ] Model endpoint verified\n- [ ] Secret and path blocking verified\n- [ ] UI smoke test verified\n\n#### Final Recommendation\nNot checked yet. Run Full Safe Audit first.`;
  };

  const currentPreview = getTemplateContent(selectedTemplate.label);

  return (
    <div className="thin-scrollbar h-full overflow-auto bg-shell p-6 text-zinc-100">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-zinc-200">Reports Generator</h2>
        <p className="text-xs text-zinc-400 mt-1">Export clean audit status summaries and handoff logs</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Available Blueprints</h3>
          {reportTemplates.map((item) => {
            const Icon = item.icon;
            const active = selectedTemplate.label === item.label;
            return (
              <button
                key={item.label}
                onClick={() => setSelectedTemplate(item)}
                className={cx(
                  "flex w-full items-start gap-3 rounded-xl border p-4 text-left transition-all",
                  active
                    ? "border-agent bg-agent/10 text-zinc-100"
                    : "border-line bg-panel text-zinc-400 hover:border-line/80 hover:text-zinc-200",
                )}
              >
                <Icon className={cx("mt-0.5 h-4 w-4 shrink-0", active ? "text-agent" : "text-zinc-500")} />
                <div className="min-w-0">
                  <div className="text-xs font-bold text-zinc-100">{item.label}</div>
                  <p className="mt-1 text-[11px] leading-4 text-zinc-500">{item.body}</p>
                </div>
              </button>
            );
          })}
        </div>

        <div className="lg:col-span-2 premium-card p-5 flex flex-col justify-between min-h-[400px]">
          <div>
            <div className="flex items-center justify-between border-b border-line pb-2 mb-4">
              <span className="text-sm font-bold text-zinc-300">Report Preview: {selectedTemplate.label}</span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleCopy(currentPreview)}
                  className="flex h-7 items-center gap-1 rounded bg-agent/15 border border-agent/30 px-3 text-xs text-agent hover:bg-agent/25 transition-colors"
                >
                  <Copy className="h-3.5 w-3.5" />
                  {copied ? "Copied!" : "Copy Report"}
                </button>
                <button
                  onClick={() => handleExport(currentPreview)}
                  className="flex h-7 items-center gap-1 rounded border border-line px-3 text-xs text-zinc-400 hover:border-agent/50 hover:text-agent transition-colors"
                >
                  <Download className="h-3.5 w-3.5" />
                  Export
                </button>
              </div>
            </div>
            <pre className="rounded border border-line bg-panel p-4 font-mono text-xs leading-5 text-zinc-300 whitespace-pre-wrap overflow-auto">
              {currentPreview}
            </pre>
          </div>
          <div className="mt-4 text-[10px] text-zinc-500">
            Note: This report is dynamically compiled from the current workspace memory and safe command outputs.
          </div>
        </div>
      </div>

      {/* ── Export QA Report section ─────────────────────────────────── */}
      <div className="mt-8 premium-card p-5">
        <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-agent" />
            <h3 className="text-xs font-bold uppercase tracking-wide text-zinc-300">Backend QA Report</h3>
            <span className="rounded bg-iris/10 border border-iris/20 text-iris px-2 py-0.5 text-[10px] font-semibold">
              Live from /api/qa/report
            </span>
          </div>
          <div className="flex items-center gap-2">
            {qaReportText && (
              <button
                onClick={handleCopyQAReport}
                className="flex h-7 items-center gap-1.5 rounded bg-agent/15 border border-agent/30 px-3 text-xs text-agent hover:bg-agent/25 transition-colors"
              >
                <Copy className="h-3.5 w-3.5" />
                {qaReportCopied ? "Copied!" : "Copy"}
              </button>
            )}
            <button
              onClick={handleExportQAReport}
              disabled={qaReportLoading}
              className="flex h-7 items-center gap-1.5 rounded border border-agent/40 bg-agent/10 px-3 text-xs font-semibold text-agent hover:bg-agent/20 disabled:cursor-not-allowed disabled:text-zinc-600 transition-colors"
            >
              {qaReportLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
              {qaReportLoading ? "Generating…" : "Export QA Report"}
            </button>
          </div>
        </div>
        <p className="text-[11px] text-zinc-500 mb-3">
          Calls <span className="font-mono text-agent">GET /api/qa/report</span> — assembles a live markdown report from in-memory backend values only. No shell, no file writes, no secrets.
        </p>
        {qaReportText && (
          <pre className="rounded border border-line bg-panel p-4 font-mono text-xs leading-5 text-zinc-300 whitespace-pre-wrap overflow-auto max-h-64">
            {qaReportText}
          </pre>
        )}
        {!qaReportText && !qaReportLoading && (
          <p className="text-xs text-zinc-600 italic">Click 'Export QA Report' to generate and download the live system report.</p>
        )}
      </div>
    </div>
  );
}

function SafetyPage() {
  const policies = [
    { label: "Patch Mode Status", value: "OFF — all file modify endpoints are strictly read-only", icon: Lock, tone: "text-honey" },
    { label: "Terminal Policy", value: "Locked safe commands only — no free input or escape chars", icon: ShieldCheck, tone: "text-mint" },
    { label: "Secrets Guard", value: ".env, id_rsa, keys, passwords — automatically blocked", icon: Lock, tone: "text-mint" },
    { label: "OCR platform directory", value: "Read-only workspace block", icon: ShieldCheck, tone: "text-mint" },
    { label: "Subprocess constraints", value: "shell=False, explicit timeout constraints active", icon: Code2, tone: "text-mint" },
    { label: "Code patching checks", value: "Requires human review & approval before edit", icon: AlertTriangle, tone: "text-honey" },
  ];

  const qaChecklist = [
    { step: "Dashboard open", detail: "Navigate to Dashboard — verify status cards appear without errors" },
    { step: "Chat Hi", detail: "Go to Chat → type 'Hi' → agent should respond with a fast local greeting" },
    { step: "Project status (no context)", detail: "Chat: 'project status' without any context loaded → agent must say 'Run Quick Audit first'" },
    { step: "Add Range to Chat Context", detail: "Workspace → pick a file → Read Range → click 'Add to Chat Context' → confirm context badge increments" },
    { step: "Full Safe Audit", detail: "Audit page → click 'Run Full Safe Audit' → all 6 steps must run and a Health rating must appear" },
    { step: "C:\\ blocked", detail: "Workspace → enter 'C:\\' in path input → verify access is denied with an error message" },
    { step: ".env blocked", detail: "Workspace → attempt to open any .env file → verify it is locked and unreadable" },
  ];

  return (
    <div className="thin-scrollbar h-full overflow-auto bg-shell p-6 text-zinc-100">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-zinc-200">Security & Safety Policy</h2>
        <p className="text-xs text-zinc-400 mt-1">Grounded local rules safeguarding the host environment</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {policies.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="premium-card p-4 flex items-start gap-3">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-panel text-zinc-400 border border-line">
                <Icon className={cx("h-4 w-4", item.tone)} />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-zinc-200">{item.label}</div>
                <p className="mt-1 text-xs text-zinc-400 leading-5">{item.value}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-8 premium-card p-5">
        <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 border-b border-line pb-2 mb-3">Allowed Roots Directory</h3>
        <div className="space-y-2.5">
          {allowedRoots.map((root) => (
            <div key={root} className="flex items-center gap-2.5 text-xs text-zinc-300 font-mono">
              <FolderOpen className="h-4 w-4 text-honey" />
              <span>{root}</span>
              <span className="rounded bg-panel border border-line px-1.5 py-0.5 text-[9px] text-zinc-500 uppercase tracking-wider">Mounted</span>
            </div>
          ))}
        </div>
      </div>

      {/* Manual QA Checklist */}
      <div className="mt-8 premium-card p-5">
        <div className="flex items-center gap-2 border-b border-line pb-3 mb-4">
          <ClipboardCheck className="h-4 w-4 text-agent" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300">Manual QA Checklist — v3.3</h3>
          <span className="ml-auto rounded bg-honey/10 border border-honey/30 px-2 py-0.5 text-[10px] font-semibold text-honey uppercase">Human Verify</span>
        </div>
        <p className="mb-4 text-[11px] text-zinc-500 leading-4">
          Run these 7 steps in order after every deployment. Only <span className="text-agent font-semibold">Full Safe Audit</span> counts as real verification — Demo Cycle does not.
        </p>
        <div className="space-y-2.5">
          {qaChecklist.map((item, idx) => (
            <div key={item.step} className="flex items-start gap-3 rounded border border-line bg-[#1a1917] px-3 py-2.5">
              <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-zinc-600 text-[10px] font-bold text-zinc-500 mt-0.5">
                {idx + 1}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-zinc-200">{item.step}</div>
                <p className="mt-0.5 text-[11px] leading-4 text-zinc-500">{item.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Model Benchmark Card ─────────────────────────────────────────────────
// Standalone display-only component — no side effects.
type BenchmarkResult = {
  model: string;
  ok: boolean;
  duration_ms: number;
  timeout_used?: number;
  recommendation?: string;
  error?: boolean;
};

function ModelBenchmarkCard({ result, running }: { result: BenchmarkResult | null; running: boolean }) {
  if (running) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-line bg-panel p-4 text-xs text-zinc-400">
        <Loader2 className="h-4 w-4 animate-spin text-agent" />
        <span>Testing <span className="font-mono text-zinc-300">{result?.model ?? "model"}</span>…</span>
      </div>
    );
  }
  if (!result) return null;
  return (
    <div className={cx(
      "rounded-lg border p-4 space-y-2.5",
      result.ok
        ? "border-mint/30 bg-mint/5"
        : "border-tomato/30 bg-tomato/5",
    )}>
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs font-semibold text-zinc-200 truncate max-w-[60%]" title={result.model}>
          {result.model}
        </span>
        <span className={cx(
          "rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
          result.ok ? "bg-mint/15 text-mint" : "bg-tomato/15 text-tomato",
        )}>
          {result.ok ? "OK" : "FAILED"}
        </span>
      </div>
      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
        <div className="flex justify-between gap-2">
          <span className="text-zinc-500">Duration</span>
          <span className="font-mono text-zinc-200">{result.duration_ms.toLocaleString()} ms</span>
        </div>
        {result.timeout_used != null && (
          <div className="flex justify-between gap-2">
            <span className="text-zinc-500">Timeout</span>
            <span className="font-mono text-zinc-200">{result.timeout_used}s</span>
          </div>
        )}
      </div>
      {/* Recommendation */}
      {result.recommendation && (
        <div className="rounded border border-line bg-panel/60 px-2.5 py-1.5 text-[11px] leading-4 text-zinc-400">
          <span className="font-semibold text-zinc-300">Recommendation: </span>
          {result.recommendation}
        </div>
      )}
    </div>
  );
}

function SettingsPage({
  activeModel,
  setActiveModel,
  responseLength,
  setResponseLength,
  temperature,
  setTemperature,
  onTestModel,
  modelTestRunning,
  backendOnline,
}: {
  activeModel: ModelKey;
  setActiveModel: (m: ModelKey) => void;
  responseLength: ResponseLength;
  setResponseLength: (rl: ResponseLength) => void;
  temperature: number;
  setTemperature: (t: number) => void;
  onTestModel: () => void;
  modelTestRunning: boolean;
  backendOnline: boolean | null;
}) {
  // Local benchmark state — doesn’t affect root App state or chat flow.
  const [singleResult, setSingleResult] = useState<BenchmarkResult | null>(null);
  const [singleRunning, setSingleRunning] = useState(false);
  const [batchResults, setBatchResults] = useState<Record<string, BenchmarkResult | "running" | null>>({});
  const [batchRunning, setBatchRunning] = useState(false);

  const runSingleBenchmark = () => {
    if (singleRunning || batchRunning) return;
    if (!backendOnline) {
      setSingleResult({ model: activeModel, ok: false, duration_ms: 0, recommendation: "Backend bridge offline — start RUN_WEB_V2.ps1" });
      return;
    }
    setSingleRunning(true);
    setSingleResult({ model: activeModel, ok: false, duration_ms: 0 }); // placeholder while running
    testModelBridge(activeModel, temperature).then((res) => {
      setSingleRunning(false);
      if (!res) {
        setSingleResult({ model: activeModel, ok: false, duration_ms: 0, recommendation: "No response from backend" });
        return;
      }
      setSingleResult({
        model: res.model,
        ok: res.ok,
        duration_ms: res.duration_ms,
        timeout_used: res.timeout_used,
        recommendation: res.recommendation ?? res.message,
        error: res.error,
      });
    });
  };

  const runAllBenchmarks = async () => {
    if (singleRunning || batchRunning) return;
    setBatchRunning(true);
    const init: Record<string, BenchmarkResult | "running" | null> = {};
    availableModels.forEach((m) => { init[m] = "running"; });
    setBatchResults(init);

    for (const model of availableModels) {
      if (!backendOnline) {
        setBatchResults((prev) => ({ ...prev, [model]: { model, ok: false, duration_ms: 0, recommendation: "Backend offline" } }));
        continue;
      }
      const res = await testModelBridge(model, temperature);
      setBatchResults((prev) => ({
        ...prev,
        [model]: res
          ? { model: res.model, ok: res.ok, duration_ms: res.duration_ms, timeout_used: res.timeout_used, recommendation: res.recommendation ?? res.message, error: res.error }
          : { model, ok: false, duration_ms: 0, recommendation: "No response from backend" },
      }));
    }
    setBatchRunning(false);
  };

  return (
    <div className="thin-scrollbar h-full overflow-auto bg-shell p-6 text-zinc-100">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-zinc-200">System Settings</h2>
        <p className="text-xs text-zinc-400 mt-1">Configure active local models and generation settings</p>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* Model selector + benchmark */}
        <div className="premium-card p-5 space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-zinc-500 block">Active LLM Model</label>
          <select
            value={activeModel}
            onChange={(e) => setActiveModel(e.target.value as ModelKey)}
            className="h-9 w-full rounded border border-line bg-panel px-3 text-sm text-zinc-200 outline-none hover:border-agent/50"
          >
            {availableModels.map((m) => (
              <option key={m} value={m}>{m === "auto" ? "Auto Router (best model)" : m}</option>
            ))}
          </select>
          <p className="text-[10px] text-zinc-500">
            Uses local Ollama models. qwen2.5-coder:7b is recommended for coding tasks.
          </p>

          {/* Benchmark actions */}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={runSingleBenchmark}
              disabled={singleRunning || batchRunning}
              className="flex h-8 items-center gap-2 rounded border border-line px-3 text-xs font-semibold text-zinc-300 hover:border-agent/50 hover:text-agent disabled:cursor-not-allowed disabled:text-zinc-600 transition-colors"
            >
              {singleRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <TestTube2 className="h-3.5 w-3.5" />}
              Test Active Model
            </button>
            <button
              type="button"
              onClick={runAllBenchmarks}
              disabled={singleRunning || batchRunning}
              className="flex h-8 items-center gap-2 rounded border border-agent/30 bg-agent/8 px-3 text-xs font-semibold text-agent hover:bg-agent/15 disabled:cursor-not-allowed disabled:text-zinc-600 transition-colors"
            >
              {batchRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Activity className="h-3.5 w-3.5" />}
              Test All Models
            </button>
          </div>

          {/* Single model result */}
          <ModelBenchmarkCard result={singleResult} running={singleRunning} />

          {/* Batch results */}
          {Object.keys(batchResults).length > 0 && (
            <div className="space-y-2.5">
              <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-500">All Models Benchmark</div>
              {availableModels.map((model) => {
                const r = batchResults[model];
                if (r === "running") {
                  return (
                    <div key={model} className="flex items-center gap-2 rounded-lg border border-line bg-panel p-4 text-xs text-zinc-400">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-agent" />
                      <span className="font-mono text-zinc-300">{model}</span>
                      <span className="text-zinc-600">testing…</span>
                    </div>
                  );
                }
                if (!r) return null;
                return <ModelBenchmarkCard key={model} result={r} running={false} />;
              })}
            </div>
          )}
        </div>

        {/* Response Length */}
        <div className="premium-card p-5">
          <label className="text-xs font-bold uppercase tracking-wider text-zinc-500 block mb-2">Response length</label>
          <div className="grid grid-cols-3 gap-2">
            {(["Quick", "Balanced", "Detailed"] as ResponseLength[]).map((rl) => (
              <button
                key={rl}
                onClick={() => setResponseLength(rl)}
                className={cx(
                  "rounded-lg border py-2 text-xs font-semibold transition-all",
                  responseLength === rl
                    ? "border-agent bg-agent/10 text-zinc-100"
                    : "border-line bg-panel text-zinc-500 hover:border-zinc-500 hover:text-zinc-300",
                )}
              >
                {rl}
              </button>
            ))}
          </div>
        </div>

        {/* Temperature */}
        <div className="premium-card p-5">
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-bold uppercase tracking-wider text-zinc-500">LLM Temperature</label>
            <span className="font-mono text-sm text-zinc-300 font-bold">{temperature.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={temperature}
            onChange={(e) => setTemperature(Number(e.target.value))}
            className="w-full accent-agent cursor-pointer"
          />
          <div className="mt-2 flex justify-between text-[10px] text-zinc-500">
            <span>0.00 (Deterministic)</span>
            <span>0.50 (Balanced)</span>
            <span>1.00 (Creative)</span>
          </div>
        </div>

        <div className="rounded-xl border border-line bg-panel p-4 flex items-center justify-between text-xs">
          <span className="text-zinc-400">Current Theme:</span>
          <span className="rounded bg-iris/10 border border-iris/20 text-iris px-2.5 py-0.5 font-bold uppercase">
            Dark Premium Agent Theme
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Code Pane ───────────────────────────────────────────────────────────────
function CodePane({ file }: { file: FileItem }) {
  const lines = file.content.split("\n");
  return (
    <div className="thin-scrollbar h-full overflow-auto bg-[#141311]">
      <div className="sticky top-0 z-10 flex h-9 items-center justify-between border-b border-line bg-[#141311]/95 px-4 backdrop-blur">
        <div className="flex min-w-0 items-center gap-2">
          <FileCode2 className={cx("h-3.5 w-3.5 shrink-0", fileTone[file.status])} />
          <span className="min-w-0 truncate text-xs text-zinc-300">{file.path}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-[10px] text-zinc-600">
          <span className="rounded border border-line px-1.5 py-0.5">{file.language}</span>
          <span>{file.lines} lines</span>
        </div>
      </div>
      <pre className="py-3 font-mono text-[12px] leading-6 text-zinc-300">
        {lines.map((line, i) => (
          <div key={`${file.id}-${i}`} className="flex min-w-max px-3 hover:bg-[#1e1c18]">
            <span className="mr-4 w-8 select-none text-right text-zinc-600">{i + 1}</span>
            <code className="whitespace-pre">{line || " "}</code>
          </div>
        ))}
      </pre>
    </div>
  );
}

// ─── Live File Pane ──────────────────────────────────────────────────────────
function LiveFilePane({
  backendOnline,
  previewPath,
  previewLines,
  previewError,
  previewLoading,
  previewStart,
  previewEnd,
  previewDurationMs,
  setPreviewStart,
  setPreviewEnd,
  onReadRange,
  onAddRangeToContext,
  rangeContextChunks,
  onLoadRoot,
  onRunAudit,
}: {
  backendOnline: boolean | null;
  previewPath: string | null;
  previewLines: FileLine[];
  previewError: string | null;
  previewLoading: boolean;
  previewStart: number;
  previewEnd: number;
  previewDurationMs: number | null;
  setPreviewStart: (v: number) => void;
  setPreviewEnd: (v: number) => void;
  onReadRange: (start: number, end: number) => void;
  onAddRangeToContext: () => void;
  rangeContextChunks: ChatContextChunk[];
  onLoadRoot: () => void;
  onRunAudit: () => void;
}) {
  // Empty state
  if (!previewPath && !previewError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-[#141311] p-8">
        <div className="grid h-12 w-12 place-items-center rounded-lg border border-line bg-panel text-zinc-600">
          <Files className="h-6 w-6" />
        </div>
        <div className="text-center">
          <h2 className="text-sm font-medium text-zinc-300">No file selected</h2>
          <p className="mt-1 text-xs text-zinc-600">
            Open the Workspace panel, pick a root, then click a file to preview it here.
          </p>
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          <button
            onClick={onLoadRoot}
            className="flex items-center gap-2 rounded border border-line bg-panel px-3 py-2 text-xs text-zinc-300 hover:border-agent/50 hover:text-zinc-100 transition-colors"
          >
            <FolderOpen className="h-3.5 w-3.5 text-honey" />
            Open AGENT_ALINE_X root
          </button>
          <button
            onClick={onRunAudit}
            className="flex items-center gap-2 rounded border border-line bg-panel px-3 py-2 text-xs text-zinc-300 hover:border-agent/50 hover:text-zinc-100 transition-colors"
          >
            <ShieldCheck className="h-3.5 w-3.5 text-mint" />
            Run Full Safe Audit
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="thin-scrollbar flex h-full flex-col overflow-auto bg-[#141311]">
      {/* Header with file path + range controls */}
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b border-line bg-[#141311]/95 px-4 py-2 backdrop-blur">
        <FileCode2 className="h-3.5 w-3.5 shrink-0 text-agent" />
        <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-zinc-300" title={previewPath ?? ""}>
          {previewPath ?? "—"}
        </span>

        {/* Range controls */}
        <div className="flex shrink-0 items-center gap-1.5 text-[11px]">
          <span className="text-zinc-600">Lines</span>
          <input
            type="number"
            value={previewStart}
            onChange={(e) => setPreviewStart(Number(e.target.value))}
            className="h-6 w-14 rounded border border-line bg-[#0f0e0d] px-1 text-center text-zinc-200 outline-none focus:border-agent/50"
          />
          <span className="text-zinc-600">—</span>
          <input
            type="number"
            value={previewEnd}
            onChange={(e) => setPreviewEnd(Number(e.target.value))}
            className="h-6 w-14 rounded border border-line bg-[#0f0e0d] px-1 text-center text-zinc-200 outline-none focus:border-agent/50"
          />
          <button
            disabled={!previewPath}
            onClick={() => onReadRange(previewStart, previewEnd)}
            className="flex h-6 items-center gap-1 rounded bg-agent px-2 text-[10px] font-semibold text-[#06211f] disabled:cursor-not-allowed disabled:bg-line disabled:text-zinc-500 hover:bg-[#5eead4] transition-colors"
          >
            {previewLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Search className="h-3 w-3" />}
            Read Range
          </button>
          <button
            disabled={!previewPath || previewLines.length === 0}
            onClick={onAddRangeToContext}
            className="flex h-6 items-center gap-1 rounded border border-line px-2 text-[10px] font-semibold text-zinc-300 hover:border-agent/50 hover:text-agent disabled:cursor-not-allowed disabled:text-zinc-600"
          >
            <Plus className="h-3 w-3" />
            Add to Chat Context
          </button>
          {previewDurationMs !== null && (
            <span className="text-zinc-600">{previewDurationMs}ms</span>
          )}
          <span className="text-zinc-600">{rangeContextChunks.length} added</span>
        </div>
      </div>

      {/* Offline / error banners */}
      {backendOnline === false && (
        <div className="m-4 rounded border border-tomato/30 bg-tomato/8 p-3 text-sm text-tomato">
          Backend bridge offline — start RUN_WEB_V2.ps1.
        </div>
      )}
      {backendOnline !== false && previewError && (
        <div className="m-4 flex items-start gap-2 rounded border border-honey/30 bg-honey/8 p-3 text-sm text-honey">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="break-words">{previewError}</span>
        </div>
      )}

      {/* File content */}
      {previewLines.length > 0 && (
        <pre className="flex-1 py-3 font-mono text-[12px] leading-6 text-zinc-300">
          {previewLines.map((entry) => (
            <div key={entry.line} className="flex min-w-max px-3 hover:bg-[#1e1c18]">
              <span className="mr-4 w-10 select-none text-right text-zinc-600">{entry.line}</span>
              <code className="whitespace-pre">{entry.text || " "}</code>
            </div>
          ))}
        </pre>
      )}

      {backendOnline !== false && !previewError && previewLines.length === 0 && (
        <p className="m-4 text-sm text-zinc-600">No content loaded — click a file in the Live File Explorer.</p>
      )}
    </div>
  );
}

// ─── Info Block ──────────────────────────────────────────────────────────────
function InfoBlock({ icon: Icon, label, value, detail }: { icon: LucideIcon; label: string; value: string; detail: string }) {
  return (
    <div className="rounded border border-line bg-[#141210] p-2.5">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-500">
        <Icon className="h-3.5 w-3.5 text-agent" />
        {label}
      </div>
      <div className="mt-1.5 truncate text-xs font-medium text-zinc-200">{value}</div>
      <div className="mt-0.5 truncate text-[11px] text-zinc-500">{detail}</div>
    </div>
  );
}

// ─── Trace Panel ─────────────────────────────────────────────────────────────
function TracePanel({
  logs,
  commandRuns,
  selectedFile,
  open,
  onToggle,
}: {
  logs: string[];
  commandRuns: CommandRun[];
  selectedFile: FileItem;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <section className="shrink-0 border-t border-line bg-[#181614]">
      {/* Collapsible header */}
      <div className="flex h-8 items-center justify-between border-b border-line px-3">
        <div className="flex items-center gap-2 text-[11px] text-zinc-500">
          <SquareTerminal className="h-3.5 w-3.5 text-agent" />
          Agent Trace
          {commandRuns.length > 0 && (
            <span className="rounded border border-line px-1 py-0.5 text-[10px] text-zinc-600">
              {commandRuns.length} run{commandRuns.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <button
          onClick={onToggle}
          className="grid h-6 w-6 place-items-center rounded text-zinc-600 hover:text-zinc-300 transition-colors"
          title={open ? "Collapse trace" : "Expand trace"}
        >
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
        </button>
      </div>

      {open && (
        <div className="grid grid-cols-[minmax(0,1fr)_320px]">
          {/* Log stream */}
          <div className="border-r border-line">
            <div className="thin-scrollbar h-[140px] overflow-auto p-2.5 font-mono text-[11px] leading-5 text-zinc-400">
              {logs.map((line, i) => (
                <div key={`${line}-${i}`} className="whitespace-pre-wrap">
                  <span className="mr-2.5 select-none text-zinc-600">
                    {String(logs.length - i).padStart(2, "0")}
                  </span>
                  {line}
                </div>
              ))}
            </div>
          </div>

          {/* Command output */}
          <div className="hidden lg:block">
            <div className="flex h-7 items-center justify-between border-b border-line px-3 text-[11px] text-zinc-500">
              <span className="flex items-center gap-1.5">
                <History className="h-3.5 w-3.5 text-honey" />
                Command Output
              </span>
              <span className="truncate text-zinc-600">{selectedFile.name}</span>
            </div>
            <div className="thin-scrollbar h-[109px] overflow-auto p-2">
              {commandRuns.length === 0 ? (
                <p className="text-[11px] text-zinc-600">No command output yet.</p>
              ) : (
                commandRuns.slice(0, 3).map((run) => (
                  <div key={run.id} className="mb-1.5 rounded border border-line bg-[#141210] p-2">
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="font-medium text-zinc-200">{run.label}</span>
                      <span className={run.exitCode === 0 ? "text-mint" : "text-tomato"}>
                        exit {run.exitCode}
                      </span>
                    </div>
                    <pre className="mt-1 whitespace-pre-wrap font-mono text-[10px] leading-4 text-zinc-500 line-clamp-2">
                      {run.output}
                    </pre>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

// ─── Agent Sidecar ───────────────────────────────────────────────────────────
function AgentSidecar({
  activeMode,
  mode,
  setMode,
  messages,
  chatInput,
  setChatInput,
  submitChat,
  isRunning,
  chatEndRef,
  onRunCycle,
  onRunCommand,
  activeModel,
}: {
  activeMode: (typeof agentModes)[number];
  mode: AgentModeKey;
  setMode: (mode: AgentModeKey) => void;
  messages: ChatMessage[];
  chatInput: string;
  setChatInput: (v: string) => void;
  submitChat: (e?: FormEvent) => void;
  isRunning: boolean;
  chatEndRef: RefObject<HTMLDivElement>;
  onRunCycle: () => void;
  onRunCommand: () => void;
  activeModel: ModelKey;
}) {
  const ActiveIcon = activeMode.icon;
  return (
    <aside className="hidden w-[360px] shrink-0 flex-col border-l border-line bg-[#1b1917] xl:flex">
      {/* Header */}
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-line px-3">
        <div className="flex items-center gap-2">
          <div className="grid h-6 w-6 shrink-0 place-items-center rounded bg-agent/15 text-agent">
            <ActiveIcon className="h-3.5 w-3.5" />
          </div>
          <div>
            <div className="text-xs font-semibold text-zinc-100">{activeMode.label} Agent</div>
            <div className="text-[10px] text-zinc-500 truncate max-w-[180px]">{activeMode.directive}</div>
          </div>
        </div>
        <div className="flex items-center gap-1 rounded border border-line px-1.5 py-0.5 text-[10px] text-mint">
          <span className="h-1.5 w-1.5 rounded-full bg-mint" />
          local · {activeModel.split("/").pop()?.slice(0, 12) ?? activeModel.slice(0, 12)}
        </div>
      </div>

      {/* Mode selector (compact) */}
      <div className="flex shrink-0 gap-0.5 border-b border-line p-1.5">
        {agentModes.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              onClick={() => setMode(item.key)}
              title={item.label}
              className={cx(
                "flex flex-1 flex-col items-center justify-center gap-0.5 rounded border py-2 text-[10px] transition-colors",
                mode === item.key
                  ? "border-agent/40 bg-agent/8 text-zinc-100"
                  : "border-transparent text-zinc-600 hover:text-zinc-300",
              )}
            >
              <Icon className={cx("h-3.5 w-3.5", item.tone)} />
              {item.label}
            </button>
          );
        })}
      </div>

      {/* Quick actions */}
      <div className="flex shrink-0 gap-1.5 border-b border-line px-3 py-2">
        <button
          onClick={onRunCycle}
          title="Demo cycle only — not a real audit or verification"
          className="flex flex-1 h-7 items-center justify-center gap-1.5 rounded border border-honey/30 bg-honey/10 text-xs font-semibold text-honey hover:bg-honey/20 transition-colors"
        >
          <Zap className="h-3 w-3" />
          Demo
        </button>
        <button
          onClick={onRunCommand}
          className="flex flex-1 h-7 items-center justify-center gap-1.5 rounded border border-line text-xs text-zinc-400 hover:border-agent/40 hover:text-zinc-200 transition-colors"
        >
          <GitBranch className="h-3 w-3" />
          Git Status
        </button>
      </div>

      {/* Messages */}
      <div className="thin-scrollbar min-h-0 flex-1 space-y-2 overflow-auto p-3">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cx(
              "rounded border px-3 py-2",
              msg.role === "user"
                ? "ml-6 border-agent/30 bg-agent/7"
                : msg.role === "system"
                  ? "border-honey/20 bg-honey/5"
                  : "mr-6 border-line bg-[#141210]",
            )}
          >
            <div className="mb-1 flex items-center justify-between text-[10px] uppercase tracking-[0.08em] text-zinc-600">
              <span>{msg.role === "user" ? "You" : msg.role}</span>
              <div className="flex items-center gap-1">
                <ChatMetaBadges msg={msg} />
                <span>{msg.time}</span>
              </div>
            </div>
            <p className="text-xs leading-5 text-zinc-200">{msg.text}</p>
          </div>
        ))}
        {isRunning && (
          <div className="mr-6 flex items-center gap-2 rounded border border-line bg-[#141210] px-3 py-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-agent" />
            <span className="text-xs text-zinc-400">Thinking…</span>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={submitChat} className="shrink-0 border-t border-line p-2.5">
        <div className="flex items-end gap-2 rounded border border-line bg-[#0f0e0d] px-3 py-2 focus-within:border-agent/50 transition-colors">
          <textarea
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submitChat();
              }
            }}
            rows={2}
            className="thin-scrollbar min-h-[44px] w-full resize-none bg-transparent text-xs text-zinc-100 outline-none placeholder:text-zinc-600"
            placeholder="Ask the agent… (Enter to send, Shift+Enter for newline)"
          />
          <button
            type="submit"
            disabled={!chatInput.trim() || isRunning}
            className="flex h-8 shrink-0 items-center gap-1.5 rounded bg-agent px-3 text-xs font-semibold text-[#06211f] disabled:cursor-not-allowed disabled:bg-line disabled:text-zinc-500 hover:bg-[#5eead4] transition-colors"
          >
            <Send className="h-3 w-3" />
            Send
          </button>
        </div>
      </form>
    </aside>
  );
}

// ─── Status Bar ──────────────────────────────────────────────────────────────
function StatusBar({
  activeView,
  selectedFile,
  commandRuns,
  contextScore,
}: {
  activeView: WorkspaceView;
  selectedFile: FileItem;
  commandRuns: CommandRun[];
  contextScore: number;
}) {
  const displayLabel = activeView === "files" 
    ? (selectedFile?.name || "no file selected")
    : (activeView === "dashboard" ? "Dashboard" : "no file selected");

  return (
    <footer className="flex h-6 shrink-0 items-center justify-between bg-[#0f766e] px-3 text-[11px] text-white">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex items-center gap-1">
          <GitBranch className="h-3 w-3" />
          local
        </span>
        <span className="hidden items-center gap-1 md:flex">
          <ShieldCheck className="h-3 w-3" />
          safe
        </span>
        <span className="min-w-0 truncate opacity-70">{displayLabel}</span>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <span>{contextScore}% ctx</span>
        <span className="hidden sm:inline opacity-70">{commandRuns[0]?.label ?? "no checks"}</span>
      </div>
    </footer>
  );
}

// ─── Command Palette ─────────────────────────────────────────────────────────
function CommandPalette({
  query,
  setQuery,
  commands,
  onClose,
}: {
  query: string;
  setQuery: (v: string) => void;
  commands: Array<{ label: string; detail: string; icon: LucideIcon; action: () => void }>;
  onClose: () => void;
}) {
  const run = (action: () => void) => {
    action();
    setQuery("");
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 pt-[10vh] backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <div
        className="mx-auto w-[min(620px,90vw)] overflow-hidden rounded-lg border border-line bg-[#1c1a18] shadow-glow"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex h-12 items-center gap-3 border-b border-line px-4">
          <Search className="h-4 w-4 shrink-0 text-agent" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-sm text-zinc-100 outline-none placeholder:text-zinc-600"
            placeholder="Search action…"
          />
          <button onClick={onClose} className="grid h-6 w-6 shrink-0 place-items-center rounded text-zinc-600 hover:text-zinc-300">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        <div className="thin-scrollbar max-h-[320px] overflow-auto p-1.5">
          {commands.map((cmd) => {
            const Icon = cmd.icon;
            return (
              <button
                key={cmd.label}
                onClick={() => run(cmd.action)}
                className="flex w-full items-center gap-3 rounded px-3 py-2.5 text-left hover:bg-panel transition-colors"
              >
                <div className="grid h-8 w-8 shrink-0 place-items-center rounded bg-agent/10 text-agent">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-zinc-100">{cmd.label}</div>
                  <div className="truncate text-[11px] text-zinc-500">{cmd.detail}</div>
                </div>
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-zinc-600" />
              </button>
            );
          })}
          {!commands.length && (
            <div className="py-6 text-center text-sm text-zinc-500">No action found</div>
          )}
        </div>
      </div>
    </div>
  );
}
