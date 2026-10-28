# AGENT ALINE X Frontend

React + TypeScript + Tailwind CSS workbench UI for AGENT ALINE X.

## Run

```powershell
cd D:\AGENT_ALINE_X_\frontend
npm.cmd install
npm.cmd run dev
```

Open: http://127.0.0.1:5173

## Build

```powershell
npm.cmd run build
```

## What is included

- VS Code-style shell with activity rail, workspace panels, code viewer, trace panel, status bar, and command palette.
- Agent modes: Architect, Builder, Tester, and Reporter.
- Real interactive frontend state for objective, context files, workflow steps, safe command output, chat, and reports.
- Safe-command cards mapped to the existing Python agent command policy.
- Browser-side agent runtime in `src/agentRuntime.ts`, ready to connect to a Python API bridge for Ollama and command execution.
- Tailwind CSS design tokens in `tailwind.config.ts`.
