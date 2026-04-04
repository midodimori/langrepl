"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useCoAgent } from "@copilotkit/react-core";

import { AGUI_URL } from "@/lib/constants";

function syntaxHighlight(json: string): string {
  return json
    .replace(
      /("(?:\\.|[^"\\])*")\s*:/g,
      '<span class="text-cyan-500">$1</span>:',
    )
    .replace(
      /:\s*("(?:\\.|[^"\\])*")/g,
      ': <span class="text-zinc-300">$1</span>',
    )
    .replace(
      /:\s*(true|false)/g,
      ': <span class="text-purple-400">$1</span>',
    )
    .replace(
      /:\s*(\d+(?:\.\d+)?)/g,
      ': <span class="text-green-400">$1</span>',
    )
    .replace(/:\s*(null)/g, ': <span class="text-zinc-600">$1</span>');
}

export function StateInspector({
  agentName,
  threadId,
}: {
  agentName: string;
  threadId: string;
}) {
  const [state, setState] = useState<Record<string, unknown> | null>(null);
  const [copied, setCopied] = useState(false);
  const [includeMessages, setIncludeMessages] = useState(false);

  const { running } = useCoAgent({ name: agentName });
  const prevRunning = useRef(false);

  const fetchState = useCallback(
    async (withMessages: boolean) => {
      try {
        const params = new URLSearchParams({ agent: agentName });
        if (withMessages) params.set("include_messages", "true");
        const res = await fetch(
          `${AGUI_URL}/threads/${threadId}/state?${params}`,
        );
        const data = await res.json();
        setState(data && Object.keys(data).length > 0 ? data : null);
      } catch {
        setState(null);
      }
    },
    [agentName, threadId],
  );

  // Fetch on mount / thread change / agent change
  useEffect(() => {
    fetchState(includeMessages);
  }, [fetchState, includeMessages]);

  // Re-fetch after agent turn completes (running: true → false)
  useEffect(() => {
    if (prevRunning.current && !running) {
      fetchState(includeMessages);
    }
    prevRunning.current = running;
  }, [running, fetchState, includeMessages]);

  const handleCopy = useCallback(() => {
    if (!state) return;
    navigator.clipboard.writeText(JSON.stringify(state, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [state]);

  const handleToggleMessages = useCallback(() => {
    const next = !includeMessages;
    setIncludeMessages(next);
    fetchState(next);
  }, [includeMessages, fetchState]);

  return (
    <div className="flex flex-col min-h-0 font-mono flex-1">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-zinc-800 shrink-0">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-zinc-600" />
          <span className="text-[11px] text-zinc-500 uppercase tracking-wide">
            state
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleToggleMessages}
            className={`px-1.5 py-0.5 text-[9px] rounded border transition-colors ${
              includeMessages
                ? "border-cyan-800 text-cyan-400 bg-cyan-950/30"
                : "border-zinc-700 text-zinc-600 hover:text-zinc-400"
            }`}
            title={
              includeMessages ? "Hide messages" : "Show messages in state"
            }
          >
            msgs
          </button>
          {state && (
            <button
              onClick={handleCopy}
              className="p-0.5 rounded text-zinc-600 hover:text-zinc-300 transition-colors"
              title="Copy state"
            >
              {copied ? (
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              ) : (
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                </svg>
              )}
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto p-2">
        {state ? (
          <pre
            className="text-[10px] leading-relaxed bg-zinc-950 border border-zinc-800 p-2 rounded whitespace-pre-wrap break-all"
            dangerouslySetInnerHTML={{
              __html: syntaxHighlight(JSON.stringify(state, null, 2)),
            }}
          />
        ) : (
          <p className="text-[11px] text-zinc-600 px-1">
            No state yet. Send a message to see agent state.
          </p>
        )}
      </div>
    </div>
  );
}
