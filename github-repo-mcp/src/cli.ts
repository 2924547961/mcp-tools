#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { baselineId, snapshotWorkingTree } from "./baseline.js";
import { SyncError } from "./auto-sync-types.js";
import { DEFAULT_CONFIG, readAutoSyncConfig, safeSync, writeAutoSyncConfig } from "./safe-sync.js";

function option(name: string): string | undefined {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

function cwd(): string {
  return path.resolve(option("path") || process.cwd());
}

function json(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

function ensureIgnored(root: string): void {
  const target = path.join(root, ".gitignore");
  const line = ".codex/github-auto-sync/";
  const current = fs.existsSync(target) ? fs.readFileSync(target, "utf8") : "";
  const lines = current.split(/\r?\n/).map(value => value.trim());
  if (!lines.includes(line)) {
    const prefix = current && !current.endsWith("\n") ? "\n" : "";
    fs.appendFileSync(target, `${prefix}${line}\n`);
  }
}

function detectChecks(root: string): Array<{ command: string; args: string[] }> {
  const candidates = [root, ...fs.readdirSync(root, { withFileTypes: true })
    .filter(entry => entry.isDirectory())
    .map(entry => path.join(root, entry.name))];
  for (const candidate of candidates) {
    const packagePath = path.join(candidate, "package.json");
    if (!fs.existsSync(packagePath)) continue;
    const pkg = JSON.parse(fs.readFileSync(packagePath, "utf8")) as { scripts?: Record<string, string> };
    const relative = path.relative(root, candidate);
    const prefix = relative ? ["--prefix", relative] : [];
    if (pkg.scripts?.check) return [{ command: "npm", args: [...prefix, "run", "check"] }];
    const names = ["test", "typecheck", "lint", "build"].filter(name => pkg.scripts?.[name]);
    if (names.length) return names.map(name => ({ command: "npm", args: [...prefix, "run", name] }));
  }
  if (fs.existsSync(path.join(root, "Cargo.toml"))) return [{ command: "cargo", args: ["test"] }];
  if (fs.existsSync(path.join(root, "go.mod"))) return [{ command: "go", args: ["test", "./..."] }];
  if (["pyproject.toml", "pytest.ini", "setup.cfg"].some(file => fs.existsSync(path.join(root, file)))) {
    return [{ command: "python", args: ["-m", "pytest"] }];
  }
  return [];
}

async function setup(): Promise<void> {
  const root = cwd();
  const inside = execFileSync("git", ["-C", root, "rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
  if (path.resolve(inside) !== root) throw new Error(`Refusing setup below another repository root: ${inside}`);
  ensureIgnored(root);
  const existing = readAutoSyncConfig(root);
  const detected = detectChecks(root);
  const config = {
    ...DEFAULT_CONFIG,
    ...existing,
    checks: existing.checks.length ? existing.checks : detected,
    allowWithoutChecks: existing.checks.length ? existing.allowWithoutChecks : detected.length === 0 ? false : existing.allowWithoutChecks,
  };
  writeAutoSyncConfig(root, config);
  json({ status: "success", root, config, ignoredStateDirectory: true });
}

async function doctor(): Promise<void> {
  const root = cwd();
  const version = (command: string, args: string[]) => {
    try { return execFileSync(command, args, { encoding: "utf8" }).trim(); }
    catch { return null; }
  };
  json({
    os: `${process.platform} ${process.arch}`,
    node: process.version,
    npm: version("npm", ["--version"]),
    git: version("git", ["--version"]),
    codex: version("codex", ["--version"]),
    gh: version("gh", ["--version"]),
    root,
    config: fs.existsSync(path.join(root, ".github-auto-sync.json")) ? readAutoSyncConfig(root) : null,
  });
}

async function main(): Promise<void> {
  const command = process.argv[2] || "status";
  if (command === "setup") return setup();
  if (command === "doctor") return doctor();
  if (command === "pause" || command === "resume") {
    const root = cwd();
    const config = readAutoSyncConfig(root);
    config.enabled = command === "resume";
    writeAutoSyncConfig(root, config);
    json({ status: "success", enabled: config.enabled, root });
    return;
  }
  if (command === "status") {
    const root = cwd();
    json({ root, config: readAutoSyncConfig(root) });
    return;
  }
  if (command === "baseline") {
    const sessionId = option("session") || "manual";
    const turnId = option("turn") || new Date().toISOString().replace(/[:.]/g, "-");
    json(await snapshotWorkingTree(cwd(), sessionId, turnId));
    return;
  }
  if (command === "sync" || command === "dry-run") {
    const sessionId = option("session") || "manual";
    const turnId = option("turn");
    const id = option("baseline") || (turnId ? baselineId(sessionId, turnId) : undefined);
    if (!id) throw new Error("Provide --baseline ID or --turn ID.");
    json(await safeSync({
      localPath: cwd(),
      baselineId: id,
      expectedBranch: option("branch"),
      remoteName: option("remote"),
      commitMessage: option("message"),
      dryRun: command === "dry-run",
    }));
    return;
  }
  if (command === "uninstall") {
    throw new SyncError("permission_required", "Use the installer uninstall command so only managed hook entries and files are removed.");
  }
  throw new Error(`Unknown command: ${command}`);
}

main().catch(error => {
  const output = error instanceof SyncError
    ? { status: error.code, error: error.message, details: error.details }
    : { status: "environment_missing", error: error instanceof Error ? error.message : String(error) };
  json(output);
  process.exitCode = 1;
});
