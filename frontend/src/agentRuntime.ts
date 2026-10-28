import { agentModes, safeCommands, workspaceFiles } from "./data";
import type { AgentModeKey, CommandRun, FileItem, WorkflowStep } from "./types";

export const formatTime = () =>
  new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());

const GREETINGS = ["hi", "hello", "hey", "vanakkam", "yo", "hai", "good morning", "good evening"];

function isGreeting(text: string): boolean {
  const cleaned = text.trim().toLowerCase().replace(/[!?.]/g, "");
  if (GREETINGS.includes(cleaned)) return true;
  const words = cleaned.split(/\s+/);
  return words.length <= 3 && words.some((w) => GREETINGS.includes(w));
}

export function buildAgentReply(params: {
  prompt: string;
  mode: AgentModeKey;
  objective: string;
  contextFiles: FileItem[];
  lastCommand?: CommandRun;
}) {
  const rawPrompt = params.prompt;
  const prompt = rawPrompt.toLowerCase();
  const mode = agentModes.find((item) => item.key === params.mode) ?? agentModes[0];
  const files = params.contextFiles.map((file) => file.name).join(", ") || "no files loaded";
  const commandLine = params.lastCommand
    ? `Last check: ${params.lastCommand.label} exit ${params.lastCommand.exitCode}.`
    : "No command output loaded yet.";

  if (isGreeting(rawPrompt)) {
    return "Vanakkam! AGENT ALINE X ready. Load context from Workspace or run a Safe Command, then ask me about project status.";
  }

  if (params.contextFiles.length === 0 && !params.lastCommand &&
      (prompt.includes("status") || prompt.includes("project") || prompt.includes("risk") || prompt.includes("audit"))) {
    return "Not Checked — no context loaded yet. Run Quick Audit first, or load a file from Workspace, then ask again.";
  }

  if (prompt.includes("plan") || params.mode === "architect") {
    return `Architect mode. Objective: ${params.objective}. Loaded context: ${files}. ${commandLine} Next: audit current state, lock scope, then create a short P0/P1/P2 plan.`;
  }

  if (prompt.includes("fix") || prompt.includes("code") || params.mode === "builder") {
    return `Builder mode. I will patch only the owning files and keep the change typed. Loaded files: ${files}. First patch target should be the smallest component or service that owns the behavior.`;
  }

  if (prompt.includes("test") || prompt.includes("verify") || params.mode === "tester") {
    return `Tester mode. Verification path: run safe commands, compare output, then report exact pass/fail. ${commandLine} I will not mark done without a build or test signal.`;
  }

  if (prompt.includes("report") || params.mode === "reporter") {
    return `Reporter mode. I will produce a client-ready summary with outcome, changed areas, checks run, remaining risk, and next action. Current objective: ${params.objective}.`;
  }

  return `${mode.label} mode active. Context: ${files}. ${commandLine} Sollu, I will handle this with audit -> plan -> patch -> verify.`;
}

export function createCommandRun(commandId: string): CommandRun {
  const command = safeCommands.find((item) => item.id === commandId) ?? safeCommands[0];
  const outputs: Record<string, string> = {
    "git-status": " M app/services/ocr.py\n M frontend/src/App.tsx\n?? frontend/src/agentRuntime.ts",
    "git-diff-stat": " app/services/ocr.py | 14 +++++++-------\n 1 file changed, 7 insertions(+), 7 deletions(-)",
    "git-diff-full": "diff --git a/app/services/ocr.py b/app/services/ocr.py\n@@ -12,7 +12,7 @@\n-old line\n+new line",
    "git-log-short": "a1b2c3d fix: ocr retry handling\n9f8e7d6 chore: update deps\n4d3c2b1 feat: add health endpoint",
    "python-compile": "Listing 'app'...\nCompiling 'app/services/ocr.py'...\nCompile check completed.",
    pytest: "18 passed, 2 skipped in 24.18s",
    "frontend-build": "vite build\n✓ 142 modules transformed.\ndist/index.html  0.46 kB\nBuild completed.",
    "backend-health": "{\"status\":\"ok\",\"service\":\"ocr-platform\",\"mode\":\"local\"}",
  };

  return {
    id: Date.now(),
    commandId,
    label: command.label,
    exitCode: 0,
    duration: command.timeout === "300s" ? "24.18s" : "1.42s",
    output: outputs[command.id] ?? "Command completed.",
    time: formatTime(),
  };
}

export function makeWorkflowState(activeIndex: number, done = false): WorkflowStep[] {
  return [
    "Audit current state",
    "Build implementation plan",
    "Prepare scoped patch",
    "Verify checks",
    "Write handoff report",
  ].map((label, index) => ({
    id: String(index),
    label: label.split(" ")[0],
    detail: label,
    state: done || index < activeIndex ? "done" : index === activeIndex ? "running" : "idle",
  }));
}

export function findFileById(fileId: string) {
  return workspaceFiles.find((file) => file.id === fileId) ?? workspaceFiles[0];
}
