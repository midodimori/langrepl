"use client";

import { useCoAgent } from "@copilotkit/react-core";

export function StepProgress({ agentName }: { agentName: string }) {
  const { running } = useCoAgent({ name: agentName });

  if (!running) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-1 bg-zinc-800/50 border-b border-zinc-800">
      <div className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
      <span className="text-[11px] text-zinc-400">Agent processing...</span>
    </div>
  );
}
