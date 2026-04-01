import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";

const AGUI_BASE_URL =
  process.env.LANGREPL_AGUI_URL || "http://localhost:8000";
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
  } catch {
    // Fallback: single default agent
    agents["default"] = new LangGraphHttpAgent({
      url: `${AGUI_BASE_URL}/agent/default`,
    });
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
