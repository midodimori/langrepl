"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { StateInspector } from "@/components/state-inspector";
import { ApprovalHandler } from "@/components/approval-handler";
import { StepProgress } from "@/components/step-progress";
import { AgentSelector } from "@/components/agent-selector";
import { ToolRenderer } from "@/components/tool-renderer";
import {
  AssistantMessageWithThinking,
  ReasoningDisplay,
} from "@/components/reasoning-display";
import { SubagentActivity } from "@/components/subagent-activity";
import { DevConsoleTheme } from "@/components/dev-console-theme";
import { ThreadSelector } from "@/components/thread-selector";
import { ThreadHistoryLoader } from "@/components/thread-history-loader";

type AgentInfo = { name: string; default: boolean };

import { AGUI_URL } from "@/lib/constants";

export default function Home() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [threadId, setThreadId] = useState<string>("");
  const [showState, setShowState] = useState(true);
  const [stateWidth, setStateWidth] = useState(360);
  const dragging = useRef(false);

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

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    const startX = e.clientX;
    const startW = stateWidth;
    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      setStateWidth(Math.max(200, Math.min(800, startW - (ev.clientX - startX))));
    };
    const onUp = () => {
      dragging.current = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [stateWidth]);

  const BoundAssistantMessage = useMemo(
    () => (props: any) => (
      <AssistantMessageWithThinking {...props} agentName={selected} />
    ),
    [selected],
  );

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
            Langrepl <span className="text-cyan-400">AG-UI</span>
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
            <button
              onClick={() => setShowState(!showState)}
              className={`px-2 py-1 text-xs rounded border transition-colors ${
                showState
                  ? "border-cyan-800 text-cyan-400 bg-cyan-950/30"
                  : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
              }`}
              title={showState ? "Hide state panel" : "Show state panel"}
            >
              {"{}"}
            </button>
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
                AssistantMessage={BoundAssistantMessage}
              />
            </div>
          </div>

          {showState && (
            <div
              className="flex flex-col border-l border-zinc-800 bg-zinc-900 shrink-0 relative"
              style={{ width: stateWidth }}
            >
              <div
                className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-cyan-800/40 transition-colors z-10"
                onMouseDown={handleResizeStart}
              />
              <StateInspector agentName={selected} threadId={threadId} />
            </div>
          )}
        </div>

        <ApprovalHandler />
        <ToolRenderer />
        <ReasoningDisplay agentName={selected} />
        <SubagentActivity agentName={selected} />
        <DevConsoleTheme />
      </div>
    </CopilotKit>
  );
}
