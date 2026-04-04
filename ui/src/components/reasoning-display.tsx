"use client";

import { useCoAgent, useCoAgentStateRender } from "@copilotkit/react-core";
import {
  AssistantMessage as DefaultAssistantMessage,
  type AssistantMessageProps,
} from "@copilotkit/react-ui";
import { useState } from "react";

type ContentBlock = { type: string; thinking?: string; [key: string]: unknown };
type LangChainMessage = {
  id?: string;
  type: string;
  content: string | ContentBlock[];
};

type AgentState = {
  messages?: LangChainMessage[];
  reasoning?: { text: string; active: boolean };
};

function extractThinking(msg: LangChainMessage): string | null {
  if (msg.type !== "ai" || !Array.isArray(msg.content)) return null;
  for (const block of msg.content) {
    if (block.type === "thinking" && block.thinking) return block.thinking;
  }
  return null;
}

/**
 * Custom AssistantMessage that prepends a collapsible thinking block
 * when the LangChain message contains thinking content.
 */
export function AssistantMessageWithThinking(
  props: AssistantMessageProps & { agentName: string },
) {
  const { agentName, ...assistantProps } = props;
  const { state } = useCoAgent<AgentState>({ name: agentName });

  // Match CopilotKit message to LangChain message by ID
  const messageId = (assistantProps as any).rawData?.id;
  let thinking: string | null = null;
  if (messageId && state?.messages) {
    const lcMsg = state.messages.find((m) => m.id === messageId);
    if (lcMsg) thinking = extractThinking(lcMsg);
  }

  return (
    <>
      {thinking && <ThinkingToggle text={thinking} />}
      <DefaultAssistantMessage {...assistantProps} />
    </>
  );
}

/**
 * Live "Thinking..." indicator during streaming (uses STATE_SNAPSHOT hack).
 */
export function ReasoningDisplay({ agentName }: { agentName: string }) {
  useCoAgentStateRender<AgentState>({
    name: agentName,
    render: ({ state, status }) => {
      if (!state?.reasoning?.active || status !== "inProgress") return null;
      return <ThinkingToggle text={state.reasoning.text} active />;
    },
  });

  return null;
}

function ThinkingToggle({
  text,
  active = false,
}: {
  text: string;
  active?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="my-2 text-[13px] font-mono">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        <span
          className={`h-2 w-2 rounded-full shrink-0 ${
            active ? "bg-cyan-400 animate-pulse" : "bg-zinc-600"
          }`}
        />
        <span>{active ? "Thinking..." : "Thought"}</span>
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 5l7 7-7 7"
          />
        </svg>
      </button>
      {expanded && (
        <pre className="mt-1.5 ml-4 text-xs text-zinc-500 whitespace-pre-wrap break-words max-h-60 overflow-auto border-l-2 border-zinc-800 pl-3 leading-relaxed">
          {text}
        </pre>
      )}
    </div>
  );
}
