import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";

import { AGUI_URL } from "@/lib/constants";

const AGUI_BASE_URL = AGUI_URL;
const serviceAdapter = new ExperimentalEmptyAdapter();

let cachedRuntime: CopilotRuntime | null = null;

async function getRuntime(): Promise<CopilotRuntime> {
  if (cachedRuntime) return cachedRuntime;

  const agents: Record<string, LangGraphHttpAgent> = {};

  try {
    const res = await fetch(`${AGUI_BASE_URL}/agents`);
    const agentList: { name: string; default: boolean }[] = await res.json();

    for (const agent of agentList) {
      agents[agent.name] = new LangGraphHttpAgent({
        url: `${AGUI_BASE_URL}/agent/${agent.name}`,
      });
    }
  } catch (err) {
    console.error("Failed to fetch agents from AG-UI server:", err);
    return new CopilotRuntime({ agents });
  }

  cachedRuntime = new CopilotRuntime({ agents });
  return cachedRuntime;
}

export const POST = async (req: NextRequest) => {
  const runtime = await getRuntime();
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
