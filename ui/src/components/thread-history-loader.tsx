"use client";

import { useEffect, useRef } from "react";
import { useCopilotChatInternal } from "@copilotkit/react-core";

import { AGUI_URL } from "@/lib/constants";

export function ThreadHistoryLoader({
  threadId,
  agentName,
}: {
  threadId: string;
  agentName: string;
}) {
  const { setMessages } = useCopilotChatInternal();
  const loadedRef = useRef<string>("");

  useEffect(() => {
    if (!setMessages || loadedRef.current === threadId) return;
    loadedRef.current = threadId;

    setMessages([]);

    let cancelled = false;

    fetch(`${AGUI_URL}/threads/${threadId}/messages?agent=${agentName}`)
      .then((res) => res.json())
      .then((msgs: { id: string; role: string; content: string }[]) => {
        if (cancelled || msgs.length === 0) return;
        setMessages(msgs);
      })
      .catch(() => {
        loadedRef.current = "";
      });

    return () => {
      cancelled = true;
    };
  }, [threadId, agentName, setMessages]);

  return null;
}
