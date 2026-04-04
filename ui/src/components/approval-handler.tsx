"use client";

import { useLangGraphInterrupt } from "@copilotkit/react-core";

export function ApprovalHandler() {
  useLangGraphInterrupt({
    render: ({ event, resolve }) => {
      const payload = event.value as {
        question?: string;
        options?: string[];
      } | null;

      const question = payload?.question || "The agent needs your approval";
      const options = payload?.options || [
        "allow",
        "always_allow",
        "deny",
        "always_deny",
      ];

      return (
        <div className="my-2 rounded border border-yellow-800 bg-zinc-900 text-xs font-mono">
          <div className="flex items-center gap-2 px-3 py-1.5 border-b border-zinc-800">
            <span className="h-2 w-2 rounded-full bg-yellow-500" />
            <span className="text-zinc-400">approval required</span>
          </div>
          <div className="px-3 py-2">
            <p className="text-zinc-300 mb-2 whitespace-pre-wrap">{question}</p>
            <div className="flex flex-wrap gap-1.5">
              {options.map((option) => (
                <button
                  key={option}
                  onClick={() => resolve(option)}
                  className={`px-2.5 py-1 rounded border text-[11px] font-medium transition-colors ${
                    option.includes("deny")
                      ? "border-red-800 text-red-400 hover:bg-red-900/50"
                      : "border-green-800 text-green-400 hover:bg-green-900/50"
                  }`}
                >
                  {option.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          </div>
        </div>
      );
    },
  });

  return null;
}
