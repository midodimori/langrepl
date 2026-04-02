"use client";

import { useEffect, useState } from "react";
import { useCopilotChat } from "@copilotkit/react-core";

type SimpleMessage = { id: string; role: string; content: string };

const AGUI_URL =
  process.env.NEXT_PUBLIC_LANGREPL_AGUI_URL || "http://localhost:8000";

export function ThreadMessagesLoader({
  threadId,
  agentName,
}: {
  threadId: string;
  agentName: string;
}) {
  const [messages, setMessages] = useState<SimpleMessage[]>([]);
  const { visibleMessages } = useCopilotChat();

  useEffect(() => {
    let cancelled = false;

    fetch(`${AGUI_URL}/threads/${threadId}/messages?agent=${agentName}`)
      .then((res) => res.json())
      .then((msgs: SimpleMessage[]) => {
        if (!cancelled) setMessages(msgs);
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      });

    return () => {
      cancelled = true;
      setMessages([]);
    };
  }, [threadId, agentName]);

  // Hide once CopilotChat has rendered its own messages (after first send)
  const copilotHasMessages = visibleMessages.length > 0;
  if (copilotHasMessages || messages.length === 0) return null;

  return (
    <div
      className="copilotKitMessages"
      style={{ flex: "none", overflow: "visible" }}
    >
      <div className="copilotKitMessagesContainer">
        {messages.map((msg) =>
          msg.role === "user" ? (
            <div
              key={msg.id}
              className="copilotKitMessage copilotKitUserMessage"
            >
              {msg.content}
            </div>
          ) : (
            <div
              key={msg.id}
              className="copilotKitMessage copilotKitAssistantMessage"
            >
              <div className="copilotKitMarkdown">
                <p className="copilotKitMarkdownElement">{msg.content}</p>
              </div>
            </div>
          ),
        )}
      </div>
    </div>
  );
}
