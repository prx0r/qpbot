/** Red-team mode: explicit tools + custom arena tools backed by the Python arena. */
import { execFile } from "node:child_process";
import { Type } from "typebox";
import { createAgentSession, DefaultResourceLoader, defineTool, getAgentDir, ModelRuntime, SessionManager } from "@earendil-works/pi-coding-agent";

const XMRECON = "/home/ubuntu/qpbot";

function arena(args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile("python3", ["-m", "core.cli", ...args], { cwd: XMRECON }, (err, stdout, stderr) => {
      if (err) reject(new Error(stderr || err.message));
      else resolve(stdout);
    });
  });
}

const probeTool = defineTool({
  name: "arena_probe",
  label: "Arena Probe",
  description: "Recon one target: returns banner and category. No flags.",
  parameters: Type.Object({ target: Type.String({ description: "Target id" }) }),
  execute: async (_id, params) => ({
    content: [{ type: "text", text: await arena(["probe", (params as any).target]) }],
    details: {},
  }),
});

const submitTool = defineTool({
  name: "arena_submit",
  label: "Arena Submit",
  description: "Submit a flag for server-side verification. Verdict is authoritative.",
  parameters: Type.Object({
    target: Type.String({ description: "Target id" }),
    flag: Type.String({ description: "Flag string" }),
  }),
  execute: async (_id, params) => ({
    content: [{
      type: "text",
      text: await arena(["submit", (params as any).target, (params as any).flag]),
    }],
    details: {},
  }),
});

const modelArg = process.argv.find((a) => a.startsWith("--model="))?.split("=")[1];
const pack = process.argv.find((a) => a.startsWith("--pack="))?.split("=")[1] ?? "demo";

const modelRuntime = await ModelRuntime.create();
const model = modelArg ? modelRuntime.getModel(...modelArg.split("/", 2) as [string, string]) : undefined;

const loader = new DefaultResourceLoader({
  cwd: process.cwd(),
  agentDir: getAgentDir(),
  systemPromptOverride: () =>
    `You are xmrecon red-team mode. Pack: ${pack}. Tools: arena_probe for recon, arena_submit for flags. ` +
    `Every claim settles server-side; only CAPTURED verdicts count. Work targets one at a time and report receipts.`,
});
await loader.reload();

const { session } = await createAgentSession({
  model,
  thinkingLevel: "medium",
  modelRuntime,
  tools: ["read", "bash", "arena_probe", "arena_submit"],
  customTools: [probeTool, submitTool],
  resourceLoader: loader,
  sessionManager: SessionManager.inMemory(),
});

session.subscribe((event) => {
  if (event.type === "message_update" && (event as any).assistantMessageEvent?.type === "text_delta") {
    process.stdout.write((event as any).assistantMessageEvent.delta);
  }
  if (event.type === "tool_execution_start") console.log(`\n[tool ${(event as any).toolName}]`);
});

await session.prompt(`List targets with arena_probe, then capture each target in pack ${pack}.`);
session.dispose();
