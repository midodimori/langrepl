"use client";

import { useState } from "react";
import { useCoAgent } from "@copilotkit/react-core";

export function StateInspector() {
  const [expanded, setExpanded] = useState(true);
  const { state } = useCoAgent({ name: "default" });

  return (
    <div className={`flex flex-col min-h-0 ${expanded ? "flex-1" : ""}`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-1.5 border-b border-zinc-800 hover:bg-zinc-800/50 transition-colors shrink-0"
      >
        <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-wide">
          State Inspector
        </h2>
        <span className="text-zinc-600 text-xs">{expanded ? "▼" : "▶"}</span>
      </button>

      {expanded && (
        <div className="flex-1 min-h-0 overflow-auto p-3">
          {state && Object.keys(state).length > 0 ? (
            <pre className="text-[10px] text-zinc-400 bg-zinc-950 p-2 rounded whitespace-pre-wrap break-all">
              {JSON.stringify(state, null, 2)}
            </pre>
          ) : (
            <p className="text-xs text-zinc-600">
              No state yet. Send a message to see agent state.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
