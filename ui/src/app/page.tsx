"use client";

import { CopilotChat } from "@copilotkit/react-ui";
import { StateInspector } from "@/components/state-inspector";
import { ApprovalHandler } from "@/components/approval-handler";
import { StepProgress } from "@/components/step-progress";
import { AgentSelector } from "@/components/agent-selector";

export default function Home() {
  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <header className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-900 shrink-0">
        <h1 className="text-sm font-bold text-zinc-300">
          Langrepl <span className="text-cyan-400">AG-UI</span> Demo
        </h1>
        <AgentSelector />
      </header>

      <div className="flex flex-1 min-h-0">
        <div className="flex-1 flex flex-col min-h-0">
          <StepProgress />
          <div className="flex-1 min-h-0">
            <CopilotChat
              className="h-full"
              labels={{
                title: "Langrepl Agent",
                initial: "Send a message to the langrepl agent...",
              }}
            />
          </div>
        </div>

        <div className="w-[360px] flex flex-col border-l border-zinc-800 bg-zinc-900 shrink-0">
          <StateInspector />
        </div>
      </div>

      <ApprovalHandler />
    </div>
  );
}
