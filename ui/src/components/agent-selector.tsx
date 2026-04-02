"use client";

type AgentInfo = { name: string; default: boolean };

export function AgentSelector({
  agents,
  selected,
  onSelect,
}: {
  agents: AgentInfo[];
  selected: string;
  onSelect: (name: string) => void;
}) {
  if (agents.length <= 1) {
    return (
      <span className="text-xs text-zinc-500">{selected || "..."}</span>
    );
  }

  return (
    <select
      value={selected}
      onChange={(e) => onSelect(e.target.value)}
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
