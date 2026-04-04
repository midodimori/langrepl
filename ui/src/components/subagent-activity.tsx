"use client";

import { useCoAgent } from "@copilotkit/react-core";
import { useEffect, useState } from "react";

type SubagentStep = {
  type: "tool" | "text";
  tool?: string;
  content?: string;
  status: "running" | "done";
};

type SubagentState = {
  agent: string;
  task: string;
  steps: SubagentStep[];
  done: boolean;
};

export function SubagentActivity({ agentName }: { agentName: string }) {
  const { state } = useCoAgent<{ subagent_activity?: SubagentState }>({
    name: agentName,
  });
  const [activity, setActivity] = useState<SubagentState | null>(null);

  useEffect(() => {
    if (state?.subagent_activity) {
      setActivity(state.subagent_activity);
    }
  }, [state?.subagent_activity]);

  if (!activity) return null;

  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-cyan-400 text-[10px] font-semibold uppercase tracking-wider">
          {activity.agent}
        </span>
      </div>
      <div className="text-zinc-500 text-[10px] mb-1.5 truncate">
        {activity.task}
      </div>
      <div className="border-l border-zinc-700 pl-3 space-y-1">
        {activity.steps.map((step, i) => (
          <div key={i} className="flex items-start gap-2 text-[10px]">
            <span
              className={`mt-0.5 h-1.5 w-1.5 rounded-full shrink-0 ${
                step.status === "running"
                  ? "bg-cyan-400 animate-pulse"
                  : "bg-zinc-600"
              }`}
            />
            {step.type === "tool" ? (
              <span className="text-zinc-400">{step.tool}</span>
            ) : (
              <span className="text-zinc-500 truncate">{step.content}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
