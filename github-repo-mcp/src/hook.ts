#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { baselineId, repositoryRoot, snapshotWorkingTree, stateDirectory } from "./baseline.js";
import { SyncError } from "./auto-sync-types.js";
import { safeSync } from "./safe-sync.js";

interface HookEvent {
  cwd: string;
  session_id: string;
  turn_id: string;
  stop_hook_active?: boolean;
  last_assistant_message?: string | null;
}

async function stdinJson(): Promise<HookEvent> {
  let raw = "";
  process.stdin.setEncoding("utf8");
  for await (const chunk of process.stdin) raw += chunk;
  return JSON.parse(raw) as HookEvent;
}

function output(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function log(cwd: string, event: unknown): void {
  try {
    const dir = stateDirectory(cwd);
    fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(path.join(dir, "hook.log"), `${new Date().toISOString()} ${JSON.stringify(event)}\n`);
  } catch (error) {
    console.error(`github-auto-sync log failure: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function isExpectedIneligibleContext(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return message.includes("outside GITHUB_MCP_ALLOWED_ROOTS") || message.startsWith("Not a Git repository:");
}

async function configuredRepositoryRoot(cwd: string): Promise<string | null> {
  try {
    const root = await repositoryRoot(cwd);
    return fs.existsSync(path.join(root, ".github-auto-sync.json")) ? root : null;
  } catch (error) {
    if (isExpectedIneligibleContext(error)) return null;
    throw error;
  }
}

async function onPrompt(event: HookEvent): Promise<void> {
  try {
    if (!await configuredRepositoryRoot(event.cwd)) {
      output({ continue: true });
      return;
    }
    const baseline = await snapshotWorkingTree(event.cwd, event.session_id, event.turn_id);
    log(baseline.repositoryRoot, { event: "UserPromptSubmit", baselineId: baseline.id });
    output({
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext:
          `GitHub auto-sync baseline ${baseline.id} was captured. After completing and checking code changes, allow the Stop hook to run safe_sync. Do not stage unrelated files.`,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`github-auto-sync baseline skipped: ${message}`);
    output({ continue: true, systemMessage: `GitHub auto-sync baseline was not captured: ${message}` });
  }
}

async function onStop(event: HookEvent): Promise<void> {
  if (event.stop_hook_active) {
    output({ continue: true });
    return;
  }
  try {
    if (!await configuredRepositoryRoot(event.cwd)) {
      output({ continue: true });
      return;
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`github-auto-sync eligibility check failed: ${message}`);
    output({ continue: true, systemMessage: `GitHub auto-sync eligibility check failed: ${message}` });
    return;
  }
  const id = baselineId(event.session_id, event.turn_id);
  try {
    const result = await safeSync({
      localPath: event.cwd,
      baselineId: id,
      commitMessage: "chore: sync Codex changes",
      runChecks: true,
      verifyRemote: true,
    });
    log(result.localPath, { event: "Stop", baselineId: id, result });
    output({
      continue: true,
      systemMessage: result.verified
        ? `GitHub auto-sync verified ${result.commit} on ${result.remote}/${result.branch}.`
        : `GitHub auto-sync result: ${result.status}${result.message ? ` - ${result.message}` : ""}`,
    });
  } catch (error) {
    const code = error instanceof SyncError ? error.code : "environment_missing";
    const message = error instanceof Error ? error.message : String(error);
    console.error(`github-auto-sync stop skipped (${code}): ${message}`);
    if (code === "checks_failed") {
      output({ decision: "block", reason: `Automatic GitHub sync stopped because checks failed. Fix the checks, then finish the task again. ${message}` });
      return;
    }
    output({ continue: true, systemMessage: `GitHub auto-sync stopped (${code}): ${message}` });
  }
}

async function main(): Promise<void> {
  const mode = process.argv[2];
  const event = await stdinJson();
  if (mode === "prompt") await onPrompt(event);
  else if (mode === "stop") await onStop(event);
  else throw new Error(`Unknown hook mode: ${mode}`);
}

main().catch(error => {
  console.error(error instanceof Error ? error.message : String(error));
  output({ continue: true, systemMessage: "GitHub auto-sync hook failed safely; no commit or push was attempted." });
});
