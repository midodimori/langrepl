"use client";

import { useRenderToolCall } from "@copilotkit/react-core";

export function ToolRenderer() {
  useRenderToolCall({
    name: "*",
    render: ({ name, args, status, result }: any) => {
      const isComplete = status === "complete";
      const resultStr =
        typeof result === "string" ? result : result != null ? JSON.stringify(result) : "";
      const firstLine = resultStr.split("\n")[0]?.toLowerCase() ?? "";
      const isError =
        isComplete &&
        result != null &&
        (firstLine.startsWith("error") ||
          firstLine.startsWith("sandbox error:") ||
          firstLine.startsWith("traceback (most recent"));

      const borderColor = isError
        ? "border-red-800"
        : isComplete
          ? "border-zinc-700"
          : "border-cyan-800";

      const statusDot = isError
        ? "bg-red-500"
        : isComplete
          ? "bg-green-500"
          : "bg-cyan-400 animate-pulse";

      const statusText = isError
        ? "error"
        : isComplete
          ? "completed"
          : "running";

      return (
        <div
          className={`my-2 rounded border text-xs font-mono ${borderColor} bg-zinc-900 ${
            !isComplete ? "animate-pulse" : ""
          }`}
        >
          <div className="flex items-center gap-2 px-3 py-1.5 border-b border-zinc-800">
            <span className={`h-2 w-2 rounded-full ${statusDot}`} />
            <span className="text-zinc-300">{name}</span>
            <span className="text-zinc-600">·</span>
            <span className="text-zinc-500">{statusText}</span>
          </div>

          {args && Object.keys(args).length > 0 && (
            <div className="px-3 py-1.5 border-b border-zinc-800">
              <span className="text-zinc-500">args: </span>
              <span className="text-zinc-400">{JSON.stringify(args)}</span>
            </div>
          )}

          {isComplete && result != null && (
            <details className="px-3 py-1.5">
              <summary
                className={`cursor-pointer hover:text-zinc-300 ${
                  isError ? "text-red-400" : "text-zinc-500"
                }`}
              >
                result (
                {typeof result === "string"
                  ? result.length
                  : JSON.stringify(result).length}{" "}
                chars)
              </summary>
              <pre
                className={`mt-1 text-[10px] whitespace-pre-wrap break-all max-h-40 overflow-auto ${
                  isError ? "text-red-400" : "text-zinc-500"
                }`}
              >
                {typeof result === "string"
                  ? result
                  : JSON.stringify(result, null, 2)}
              </pre>
            </details>
          )}
        </div>
      );
    },
  });

  return null;
}
