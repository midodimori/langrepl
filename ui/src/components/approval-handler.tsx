"use client";

import { useCopilotAction } from "@copilotkit/react-core";

export function ApprovalHandler() {
  useCopilotAction({
    name: "on_interrupt",
    description: "Handle tool approval interrupts from the langrepl agent",
    available: "remote",
    parameters: [],
    renderAndWaitForResponse: ({ status, respond, args }) => {
      if (status === "complete") return <></>;

      // The interrupt payload comes from langrepl's ApprovalMiddleware
      const payload = args as {
        question?: string;
        options?: string[];
      };

      const question = payload?.question || "The agent needs your approval";
      const options = payload?.options || [
        "allow",
        "always_allow",
        "deny",
        "always_deny",
      ];

      return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 max-w-md w-full mx-4 shadow-2xl">
            <h3 className="text-sm font-bold text-zinc-200 mb-3">
              Tool Approval Required
            </h3>
            <p className="text-sm text-zinc-400 mb-4 whitespace-pre-wrap">
              {question}
            </p>
            <div className="flex flex-wrap gap-2">
              {options.map((option) => (
                <button
                  key={option}
                  onClick={() => respond?.(option)}
                  className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                    option.includes("allow")
                      ? "bg-green-700 hover:bg-green-600 text-white"
                      : "bg-red-700 hover:bg-red-600 text-white"
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
