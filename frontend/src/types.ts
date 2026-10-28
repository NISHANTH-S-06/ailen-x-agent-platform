import type { LucideIcon } from "lucide-react";

export type AgentModeKey = "architect" | "builder" | "tester" | "reporter";

export type WorkspaceView = "dashboard" | "agent" | "files" | "commands" | "audit" | "memory" | "reports" | "safety" | "settings";

export type ModelKey = "auto" | "agent-aline-x" | "maxwellb/gemma4-12b-it-oym" | "qwen2.5-coder:7b";

export type ResponseLength = "Quick" | "Balanced" | "Detailed";

export type HealthRating = "Healthy" | "Needs Attention" | "Critical";

export type AuditEvent = {
  id: number;
  label: string;
  detail: string;
  time: string;
};

export type WorkflowState = "idle" | "running" | "done" | "blocked";

export type FileStatus = "clean" | "modified" | "locked" | "new";

export type FileItem = {
  id: string;
  name: string;
  path: string;
  language: string;
  status: FileStatus;
  lines: number;
  content: string;
};

export type AgentMode = {
  key: AgentModeKey;
  label: string;
  tone: string;
  icon: LucideIcon;
  directive: string;
};

export type SafeCommand = {
  id: string;
  label: string;
  command: string;
  cwd: string;
  timeout: string;
  intent: string;
  icon: LucideIcon;
};

export type WorkflowStep = {
  id: string;
  label: string;
  detail: string;
  state: WorkflowState;
};

export type ChatMessage = {
  id: number;
  role: "user" | "agent" | "system";
  text: string;
  time: string;
  durationMs?: number;
  answerSource?: "fast_local" | "model" | "mock";
  responseLength?: string;
  status?: string;
  selectedModel?: string;
  routeReason?: string;
  fallbackUsed?: boolean;
  contextTrimmed?: boolean;
  fileContextUsed?: boolean;
  fileContextFileCount?: number;
  fileContextChars?: number;
  fileContextTrimmed?: boolean;
  memoryContextUsed?: boolean;
  memoryContextChunks?: number;
  retrievalMode?: string;
  memoryContextChars?: number;
  memoryIndexMissing?: boolean;
  memoryAutoReindexed?: boolean;
  memoryResultsFound?: number;
};

export type ChatContextChunk = {
  id: string;
  label: string;
  path: string;
  start: number;
  end: number;
  text: string;
  addedAt: string;
};

export type FailureAnalysis = {
  root_cause: string;
  likely_file: string;
  safe_fix_direction: string;
  next_test_command: string;
};

export type CommandRun = {
  id: number;
  commandId: string;
  label: string;
  exitCode: number;
  duration: string;
  output: string;
  time: string;
  failureAnalysis?: FailureAnalysis | null;
};

export type MemoryItem = {
  id: string;
  label: string;
  value: string;
  tone: string;
};
