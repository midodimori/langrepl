"use client";

import { useState } from "react";
import { useCoAgent } from "@copilotkit/react-core";

export function StateInspector({ agentName }: { agentName: string }) {
  const [expanded, setExpanded] = useState(true);
  const { state } = useCoAgent({ name: agentName });

  return (
    <div className={`flex flex-col min-h-0 font-mono ${expanded ? "flex-1" : ""}`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-1.5 border-b border-zinc-800 hover:bg-zinc-800/30 transition-colors shrink-0"
      >
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-zinc-600" />
          <span className="text-[11px] text-zinc-500 uppercase tracking-wide">
            state
          </span>
        </div>
        <span className="text-zinc-600 text-xs">{expanded ? "▼" : "▶"}</span>
      </button>

      {expanded && (
        <div className="flex-1 min-h-0 overflow-auto p-2">
          {state && Object.keys(state).length > 0 ? (
            <pre className="text-[10px] text-zinc-500 bg-zinc-950 border border-zinc-800 p-2 rounded whitespace-pre-wrap break-all">
              {JSON.stringify(state, null, 2)}
            </pre>
          ) : (
            <p className="text-[11px] text-zinc-600 px-1">
              No state yet. Send a message to see agent state.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
