"use client";

import { useState, useEffect } from "react";
import { useCopilotContext } from "@copilotkit/react-core";

type AgentInfo = { name: string; default: boolean };

export function AgentSelector() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selected, setSelected] = useState<string>("");
  const context = useCopilotContext();

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_LANGREPL_AGUI_URL || "http://localhost:8000";
    fetch(`${url}/agents`)
      .then((res) => res.json())
      .then((list: AgentInfo[]) => {
        setAgents(list);
        const defaultAgent = list.find((a) => a.default) || list[0];
        if (defaultAgent) setSelected(defaultAgent.name);
      })
      .catch(() => {
        setAgents([{ name: "default", default: true }]);
        setSelected("default");
      });
  }, []);

  if (agents.length <= 1) {
    return (
      <span className="text-xs text-zinc-500">
        {selected || "default"}
      </span>
    );
  }

  return (
    <select
      value={selected}
      onChange={(e) => setSelected(e.target.value)}
      className="text-xs bg-zinc-800 text-zinc-300 border border-zinc-700 rounded px-2 py-1 focus:outline-none focus:border-cyan-400"
    >
      {agents.map((agent) => (
        <option key={agent.name} value={agent.name}>
          {agent.name} {agent.default ? "(default)" : ""}
        </option>
      ))}
    </select>
  );
}
