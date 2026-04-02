"use client";

import { useState, useEffect, useCallback, useRef } from "react";

type ThreadInfo = {
  thread_id: string;
  last_message: string;
  timestamp: string;
  agent: string;
};

const AGUI_URL =
  process.env.NEXT_PUBLIC_LANGREPL_AGUI_URL || "http://localhost:8000";

function timeAgo(ts: string): string {
  if (!ts) return "";
  const now = Date.now();
  const then = new Date(ts).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

export function ThreadSelector({
  agentName,
  currentThreadId,
  onSelectThread,
  onNewThread,
}: {
  agentName: string;
  currentThreadId: string;
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
}) {
  const [threads, setThreads] = useState<ThreadInfo[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const fetchThreads = useCallback(async () => {
    try {
      const res = await fetch(`${AGUI_URL}/threads?agent=${agentName}`);
      const data: ThreadInfo[] = await res.json();
      setThreads(data);
    } catch {
      setThreads([]);
    }
  }, [agentName]);

  useEffect(() => {
    fetchThreads();
  }, [fetchThreads]);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const currentLabel =
    threads.find((t) => t.thread_id === currentThreadId)?.last_message ||
    "new thread";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => {
          if (!open) fetchThreads();
          setOpen(!open);
        }}
        className="text-xs bg-zinc-800 text-zinc-300 border border-zinc-700 rounded px-2 py-1 focus:outline-none focus:border-cyan-400 max-w-[160px] truncate"
      >
        {currentLabel.substring(0, 20)}
        {currentLabel.length > 20 ? "..." : ""} ▾
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 bg-zinc-900 border border-zinc-700 rounded shadow-lg z-50 max-h-80 overflow-auto font-mono">
          <button
            onClick={() => {
              onNewThread();
              setOpen(false);
            }}
            className="w-full text-left px-3 py-2 text-[11px] text-cyan-400 hover:bg-zinc-800 border-b border-zinc-800 transition-colors"
          >
            + new conversation
          </button>

          {threads.length === 0 ? (
            <p className="text-[11px] text-zinc-600 px-3 py-2">
              No past threads.
            </p>
          ) : (
            threads.map((t) => (
              <button
                key={t.thread_id}
                onClick={() => {
                  onSelectThread(t.thread_id);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-2 border-b border-zinc-800/50 transition-colors ${
                  t.thread_id === currentThreadId
                    ? "bg-zinc-800 text-zinc-200"
                    : "hover:bg-zinc-800/50 text-zinc-400"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[11px] truncate flex-1">
                    {t.last_message}
                  </span>
                  <span className="text-[10px] text-zinc-600 ml-2 shrink-0">
                    {timeAgo(t.timestamp)}
                  </span>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
