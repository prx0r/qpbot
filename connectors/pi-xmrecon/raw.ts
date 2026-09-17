/** Raw chat mode: true raw-model session. No tools, minimal prompt. */
import { createAgentSession, DefaultResourceLoader, getAgentDir, ModelRuntime, SessionManager } from "@earendil-works/pi-coding-agent";

const modelArg = process.argv.find((a) => a.startsWith("--model="))?.split("=")[1];

const modelRuntime = await ModelRuntime.create();
const model = modelArg ? modelRuntime.getModel(...modelArg.split("/", 2) as [string, string]) : undefined;

const loader = new DefaultResourceLoader({
  cwd: process.cwd(),
  agentDir: getAgentDir(),
  systemPromptOverride: () => "You are a raw model chat session. Answer directly, no tools, no harness.",
});
await loader.reload();

const { session } = await createAgentSession({
  model,
  thinkingLevel: "off",
  modelRuntime,
  noTools: "all",
  resourceLoader: loader,
  sessionManager: SessionManager.inMemory(),
});

session.subscribe((event) => {
  if (event.type === "message_update" && (event as any).assistantMessageEvent?.type === "text_delta") {
    process.stdout.write((event as any).assistantMessageEvent.delta);
  }
});

const prompt = process.argv.filter((a) => !a.startsWith("--") && a !== "raw.ts").slice(2).join(" ") || "Say hello.";
await session.prompt(prompt);
session.dispose();
