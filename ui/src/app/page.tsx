"use client";

import { useState, useEffect, useCallback } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { StateInspector } from "@/components/state-inspector";
import { ApprovalHandler } from "@/components/approval-handler";
import { StepProgress } from "@/components/step-progress";
import { AgentSelector } from "@/components/agent-selector";
import { ToolRenderer } from "@/components/tool-renderer";
import { DevConsoleTheme } from "@/components/dev-console-theme";
import { ThreadSelector } from "@/components/thread-selector";
import { ThreadHistoryLoader } from "@/components/thread-history-loader";

type AgentInfo = { name: string; default: boolean };

import { AGUI_URL } from "@/lib/constants";

export default function Home() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [threadId, setThreadId] = useState<string>("");

  useEffect(() => {
    fetch(`${AGUI_URL}/agents`)
      .then((res) => res.json())
      .then((list: AgentInfo[]) => {
        setAgents(list);
        const def = list.find((a) => a.default) || list[0];
        if (def) setSelected(def.name);
      })
      .catch(() => {});
    setThreadId(crypto.randomUUID());
  }, []);

  const handleNewThread = useCallback(() => {
    setThreadId(crypto.randomUUID());
  }, []);

  if (!selected || !threadId) {
    return (
      <div className="flex items-center justify-center h-screen text-zinc-500 text-sm">
        Connecting to AG-UI server...
      </div>
    );
  }

  return (
    <CopilotKit
      runtimeUrl="/api/copilotkit"
      agent={selected}
      threadId={threadId}
    >
      <ThreadHistoryLoader threadId={threadId} agentName={selected} />
      <div className="flex flex-col h-screen overflow-hidden">
        <header className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-900 shrink-0">
          <h1 className="text-sm font-bold text-zinc-300">
            Langrepl <span className="text-cyan-400">AG-UI</span> Demo
          </h1>
          <div className="flex items-center gap-3">
            <ThreadSelector
              agentName={selected}
              currentThreadId={threadId}
              onSelectThread={setThreadId}
              onNewThread={handleNewThread}
            />
            <AgentSelector
              agents={agents}
              selected={selected}
              onSelect={setSelected}
            />
          </div>
        </header>

        <div className="flex flex-1 min-h-0">
          <div className="flex-1 flex flex-col min-h-0">
            <StepProgress agentName={selected} />
            <div className="flex-1 min-h-0">
              <CopilotChat
                className="h-full"
                labels={{
                  title: selected,
                  initial: "",
                }}
              />
            </div>
          </div>

          <div className="w-[360px] flex flex-col border-l border-zinc-800 bg-zinc-900 shrink-0">
            <StateInspector agentName={selected} />
          </div>
        </div>

        <ApprovalHandler />
        <ToolRenderer />
        <DevConsoleTheme />
      </div>
    </CopilotKit>
  );
}
