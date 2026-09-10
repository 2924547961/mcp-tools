import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const hookPath = path.resolve(import.meta.dirname, "../src/hook.js");

function runHook(mode: "prompt" | "stop", cwd: string, allowedRoot: string) {
  const input = JSON.stringify({
    cwd,
    session_id: "hook-test-session",
    turn_id: "hook-test-turn",
    hook_event_name: mode === "prompt" ? "UserPromptSubmit" : "Stop",
    stop_hook_active: false,
  });
  const result = spawnSync(process.execPath, [hookPath, mode], {
    input,
    encoding: "utf8",
    env: { ...process.env, GITHUB_MCP_ALLOWED_ROOTS: allowedRoot },
  });
  return { ...result, output: JSON.parse(result.stdout) as Record<string, unknown> };
}

test("hook silently skips a cwd outside the allowed roots", () => {
  const allowed = fs.mkdtempSync(path.join(os.tmpdir(), "github-auto-sync-allowed-"));
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), "github-auto-sync-outside-"));
  try {
    for (const mode of ["prompt", "stop"] as const) {
      const result = runHook(mode, outside, allowed);
      assert.equal(result.status, 0);
      assert.deepEqual(result.output, { continue: true });
      assert.equal(result.stderr, "");
    }
  } finally {
    fs.rmSync(allowed, { recursive: true, force: true });
    fs.rmSync(outside, { recursive: true, force: true });
  }
});

test("hook silently skips an allowed directory that is not a repository", () => {
  const allowed = fs.mkdtempSync(path.join(os.tmpdir(), "github-auto-sync-no-repo-"));
  try {
    for (const mode of ["prompt", "stop"] as const) {
      const result = runHook(mode, allowed, allowed);
      assert.equal(result.status, 0);
      assert.deepEqual(result.output, { continue: true });
      assert.equal(result.stderr, "");
    }
  } finally {
    fs.rmSync(allowed, { recursive: true, force: true });
  }
});
