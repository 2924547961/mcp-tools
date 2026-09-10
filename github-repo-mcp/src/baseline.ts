import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { assertAllowedPath, gitExecutable } from "./config.js";
import { BaselineSnapshot, FileSnapshot, SyncError } from "./auto-sync-types.js";
import { runCommand } from "./process.js";

async function git(cwd: string, args: string[], allowExitCodes = [0]) {
  return runCommand(gitExecutable(), args, { cwd, allowExitCodes });
}

function safeId(value: string): string {
  return value.replace(/[^A-Za-z0-9._-]/g, "_").slice(0, 160);
}

export function baselineId(sessionId: string, turnId: string): string {
  return `${safeId(sessionId)}--${safeId(turnId)}`;
}

export function stateDirectory(root: string): string {
  return path.join(root, ".codex", "github-auto-sync");
}

export function baselinePath(root: string, id: string): string {
  return path.join(stateDirectory(root), "baselines", `${safeId(id)}.json`);
}

function hashFile(filePath: string): string | null {
  try {
    const stat = fs.lstatSync(filePath);
    if (!stat.isFile()) return null;
    return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
  } catch {
    return null;
  }
}

function parsePorcelainZ(raw: string): Array<{ status: string; file: string }> {
  const tokens = raw.split("\0");
  const result: Array<{ status: string; file: string }> = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (!token) continue;
    const status = token.slice(0, 2);
    let file = token.slice(3);
    if ((status.includes("R") || status.includes("C")) && tokens[index + 1]) {
      file = tokens[index + 1];
      index += 1;
    }
    result.push({ status, file });
  }
  return result;
}

export async function repositoryRoot(cwd: string): Promise<string> {
  const allowed = assertAllowedPath(cwd);
  const result = await git(allowed, ["rev-parse", "--show-toplevel"], [0, 128]);
  if (result.code !== 0) {
    throw new SyncError("environment_missing", `Not a Git repository: ${allowed}`);
  }
  return fs.realpathSync.native(result.stdout.trim());
}

export async function snapshotWorkingTree(
  cwd: string,
  sessionId: string,
  turnId: string,
): Promise<BaselineSnapshot> {
  const root = await repositoryRoot(cwd);
  const [headResult, branchResult, commonResult, statusResult, upstreamResult, remotesResult] = await Promise.all([
    git(root, ["rev-parse", "--verify", "HEAD"], [0, 128]),
    git(root, ["branch", "--show-current"]),
    git(root, ["rev-parse", "--git-common-dir"]),
    git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]),
    git(root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], [0, 128]),
    git(root, ["remote", "-v"]),
  ]);
  const id = baselineId(sessionId, turnId);
  const files: FileSnapshot[] = parsePorcelainZ(statusResult.stdout).map(entry => ({
    path: entry.file,
    status: entry.status,
    hash: hashFile(path.join(root, entry.file)),
    staged: entry.status[0] !== " " && entry.status[0] !== "?",
    untracked: entry.status === "??",
  }));
  const common = path.resolve(root, commonResult.stdout.trim());
  const snapshot: BaselineSnapshot = {
    version: 1,
    id,
    sessionId,
    turnId,
    repositoryRoot: root,
    gitCommonDir: fs.realpathSync.native(common),
    head: headResult.code === 0 ? headResult.stdout.trim() : null,
    branch: branchResult.stdout.trim() || null,
    upstream: upstreamResult.code === 0 ? upstreamResult.stdout.trim() : null,
    remotes: Object.fromEntries(
      remotesResult.stdout.split(/\r?\n/).filter(Boolean).map(line => {
        const [name, url] = line.split(/\s+/);
        return [name, url];
      }),
    ),
    createdAt: new Date().toISOString(),
    files,
  };
  const target = baselinePath(root, id);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(snapshot, null, 2)}\n`, { mode: 0o600 });
  return snapshot;
}

export function readBaseline(root: string, id: string): BaselineSnapshot {
  const target = baselinePath(root, id);
  if (!fs.existsSync(target)) {
    throw new SyncError("preexisting_changes", `Baseline not found: ${id}`, { baselineId: id });
  }
  const parsed = JSON.parse(fs.readFileSync(target, "utf8")) as BaselineSnapshot;
  if (parsed.version !== 1 || parsed.id !== id || parsed.repositoryRoot !== root) {
    throw new SyncError("preexisting_changes", `Baseline is invalid for this repository: ${id}`);
  }
  return parsed;
}

export function writeBaselineResult(root: string, id: string, result: unknown): void {
  const target = path.join(stateDirectory(root), "results", `${safeId(id)}.json`);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(result, null, 2)}\n`, { mode: 0o600 });
}

export function readBaselineResult(root: string, id: string): unknown | null {
  const target = path.join(stateDirectory(root), "results", `${safeId(id)}.json`);
  return fs.existsSync(target) ? JSON.parse(fs.readFileSync(target, "utf8")) : null;
}

export function currentFileHash(root: string, relativePath: string): string | null {
  return hashFile(path.join(root, relativePath));
}

export function parseStatus(raw: string): Array<{ status: string; file: string }> {
  return parsePorcelainZ(raw);
}
