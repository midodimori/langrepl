# Langrepl AG-UI Demo

CopilotKit frontend for the langrepl AG-UI server. Demonstrates chat streaming, state sync, step progress, and interrupt-based tool approval.

## Prerequisites

- AG-UI server running: `uv run langrepl -s --protocol agui`
- Node.js and pnpm

## Setup

```bash
pnpm install
```

## Run

```bash
# Terminal 1: start AG-UI backend
uv run langrepl -s --protocol agui

# Terminal 2: start frontend
cd ui && pnpm dev
```

Open [http://localhost:3000](http://localhost:3000).

## Configuration

Edit `.env.local` to change the AG-UI server URL:

```
NEXT_PUBLIC_LANGREPL_AGUI_URL=http://localhost:8000
```

## Structure

```
src/
├── app/
│   ├── api/copilotkit/route.ts   # CopilotKit runtime → LangGraphHttpAgent proxy
│   ├── layout.tsx                # CopilotKit provider, dark theme
│   ├── page.tsx                  # Two-panel layout: chat + state inspector
│   └── globals.css               # Tailwind + CopilotChat overrides
└── components/
    ├── approval-handler.tsx      # Interrupt dialog (tool approval)
    ├── state-inspector.tsx       # Agent state JSON viewer
    └── step-progress.tsx         # Processing indicator
```
