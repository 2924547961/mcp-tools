import fs from "node:fs";
import path from "node:path";
import { assertAllowedPath, gitExecutable } from "./config.js";
import { cloneUrlFor } from "./github.js";
import { CommandError, runCommand } from "./process.js";

const sensitiveBasenames = [
  /^\.env(?:\..+)?$/i,
  /^id_(?:rsa|dsa|ecdsa|ed25519)$/i,
  /\.(?:pem|p12|pfx|key)$/i,
  /^credentials(?:\..+)?\.json$/i,
  /^service-account.*\.json$/i,
];

async function git(cwd: string, args: string[], allowExitCodes = [0]) {
  return runCommand(gitExecutable(), args, { cwd, allowExitCodes });
}

async function isGitRepository(cwd: string): Promise<boolean> {
  try {
    await git(cwd, ["rev-parse", "--is-inside-work-tree"]);
    return true;
  } catch {
    return false;
  }
}

async function ensureIdentity(cwd: string): Promise<void> {
  const name = await git(cwd, ["config", "user.name"], [0, 1]);
  const email = await git(cwd, ["config", "user.email"], [0, 1]);
  if (name.stdout.trim() && email.stdout.trim()) {
    return;
  }

  const configuredName = process.env.GITHUB_MCP_GIT_NAME?.trim();
  const configuredEmail = process.env.GITHUB_MCP_GIT_EMAIL?.trim();
  if (!configuredName || !configuredEmail) {
    throw new Error(
      "Git commit identity is missing. Set GITHUB_MCP_GIT_NAME and GITHUB_MCP_GIT_EMAIL, or configure git user.name and user.email.",
    );
  }
  await git(cwd, ["config", "user.name", configuredName]);
  await git(cwd, ["config", "user.email", configuredEmail]);
}

async function ensureRepository(cwd: string, branch = "main"): Promise<void> {
  if (!(await isGitRepository(cwd))) {
    await git(cwd, ["init"]);
    await git(cwd, ["branch", "-M", branch]);
  }
}

async function currentBranch(cwd: string): Promise<string> {
  const result = await git(cwd, ["branch", "--show-current"]);
  const branch = result.stdout.trim();
  if (!branch) {
    throw new Error("The repository is in detached HEAD state.");
  }
  return branch;
}

async function ensureRemote(cwd: string, remoteName: string, url: string): Promise<void> {
  const current = await git(cwd, ["remote", "get-url", remoteName], [0, 2]);
  if (!current.stdout.trim()) {
    await git(cwd, ["remote", "add", remoteName, url]);
    return;
  }
  if (current.stdout.trim() !== url) {
    throw new Error(
      `Remote ${remoteName} already points to ${current.stdout.trim()}, not ${url}. Refusing to overwrite it.`,
    );
  }
}

async function untrackedFiles(cwd: string): Promise<string[]> {
  const result = await git(cwd, ["ls-files", "--others", "--exclude-standard", "-z"]);
  return result.stdout.split("\0").filter(Boolean);
}

async function assertNoSensitiveUntracked(cwd: string): Promise<void> {
  const sensitive = (await untrackedFiles(cwd)).filter(file => {
    const base = path.basename(file);
    if (/\.example$/i.test(base)) {
      return false;
    }
    return sensitiveBasenames.some(pattern => pattern.test(base));
  });
  if (sensitive.length) {
    throw new Error(
      `Refusing to stage likely sensitive files: ${sensitive.join(", ")}. Ignore them or set allowSensitiveFiles=true explicitly.`,
    );
  }
}

async function stageChanges(
  cwd: string,
  options: { includePaths?: string[]; includeUntracked?: boolean; allowSensitiveFiles?: boolean },
): Promise<void> {
  if (!options.allowSensitiveFiles && (options.includeUntracked || options.includePaths?.length)) {
    await assertNoSensitiveUntracked(cwd);
  }
  if (options.includePaths?.length) {
    await git(cwd, ["add", "--", ...options.includePaths]);
  } else if (options.includeUntracked) {
    await git(cwd, ["add", "-A"]);
  } else {
    await git(cwd, ["add", "-u"]);
  }
}

async function stagedChangesExist(cwd: string): Promise<boolean> {
  const result = await git(cwd, ["diff", "--cached", "--quiet"], [0, 1]);
  return result.code === 1;
}

async function hasHead(cwd: string): Promise<boolean> {
  const result = await git(cwd, ["rev-parse", "--verify", "HEAD"], [0, 128]);
  return result.code === 0;
}

async function commitIfNeeded(cwd: string, message: string): Promise<string | null> {
  if (!(await stagedChangesExist(cwd))) {
    return null;
  }
  await ensureIdentity(cwd);
  await git(cwd, ["commit", "-m", message]);
  return (await git(cwd, ["rev-parse", "HEAD"])).stdout.trim();
}

export async function publishCode(input: {
  localPath: string;
  repository: string;
  branch?: string;
  remoteName?: string;
  commitMessage?: string;
  includePaths?: string[];
  allowSensitiveFiles?: boolean;
}): Promise<Record<string, unknown>> {
  const cwd = assertAllowedPath(input.localPath);
  const branch = input.branch || "main";
  const remoteName = input.remoteName || "origin";
  const remoteUrl = cloneUrlFor(input.repository);
  await ensureRepository(cwd, branch);
  await ensureRemote(cwd, remoteName, remoteUrl);

  if (!(await hasHead(cwd))) {
    await git(cwd, ["branch", "-M", branch]);
  }
  await stageChanges(cwd, {
    includePaths: input.includePaths,
    includeUntracked: true,
    allowSensitiveFiles: input.allowSensitiveFiles,
  });
  const commit = await commitIfNeeded(cwd, input.commitMessage || "chore: publish repository");
  const activeBranch = await currentBranch(cwd);
  await git(cwd, ["push", "-u", remoteName, activeBranch]);
  return { localPath: cwd, repository: input.repository, branch: activeBranch, commit, pushed: true };
}

export async function syncChanges(input: {
  localPath: string;
  branch?: string;
  remoteName?: string;
  commitMessage?: string;
  includePaths?: string[];
  includeUntracked?: boolean;
  allowSensitiveFiles?: boolean;
}): Promise<Record<string, unknown>> {
  const cwd = assertAllowedPath(input.localPath);
  if (!(await isGitRepository(cwd))) {
    throw new Error("Local path is not a Git repository. Use create_and_publish or publish_code first.");
  }
  await stageChanges(cwd, input);
  const commit = await commitIfNeeded(cwd, input.commitMessage || "chore: sync code changes");
  const branch = input.branch || (await currentBranch(cwd));
  const remoteName = input.remoteName || "origin";
  if (commit) {
    await git(cwd, ["push", "-u", remoteName, branch]);
  }
  return { localPath: cwd, branch, commit, pushed: Boolean(commit), noChanges: !commit };
}

export async function pullRepository(input: {
  localPath: string;
  branch?: string;
  remoteName?: string;
  ffOnly?: boolean;
}): Promise<Record<string, unknown>> {
  const cwd = assertAllowedPath(input.localPath);
  const remoteName = input.remoteName || "origin";
  const args = ["pull"];
  if (input.ffOnly ?? true) {
    args.push("--ff-only");
  }
  args.push(remoteName, input.branch || (await currentBranch(cwd)));
  const result = await git(cwd, args);
  return { localPath: cwd, output: result.stdout.trim() || result.stderr.trim() };
}

export async function cloneRepository(input: {
  repository: string;
  targetPath: string;
  branch?: string;
  depth?: number;
}): Promise<Record<string, unknown>> {
  const target = assertAllowedPath(input.targetPath, { mustExist: false });
  if (fs.existsSync(target) && fs.readdirSync(target).length > 0) {
    throw new Error(`Clone target is not empty: ${target}`);
  }
  const parent = assertAllowedPath(path.dirname(target));
  const args = ["clone"];
  if (input.branch) {
    args.push("--branch", input.branch);
  }
  if (input.depth) {
    args.push("--depth", String(input.depth));
  }
  args.push(cloneUrlFor(input.repository), target);
  await runCommand(gitExecutable(), args, { cwd: parent });
  return { repository: input.repository, targetPath: target, cloned: true };
}

export async function repositoryStatus(localPath: string): Promise<Record<string, unknown>> {
  const cwd = assertAllowedPath(localPath);
  if (!(await isGitRepository(cwd))) {
    return { localPath: cwd, isGitRepository: false };
  }
  const status = await git(cwd, ["status", "--porcelain=v1", "--branch"]);
  const remote = await git(cwd, ["remote", "get-url", "origin"], [0, 2]);
  const lines = status.stdout.trimEnd().split(/\r?\n/).filter(Boolean);
  return {
    localPath: cwd,
    isGitRepository: true,
    branchSummary: lines[0] || "",
    changes: lines.slice(1),
    clean: lines.length <= 1,
    origin: remote.stdout.trim() || null,
  };
}

export function userFacingError(error: unknown): string {
  if (error instanceof CommandError) {
    return error.message;
  }
  return error instanceof Error ? error.message : String(error);
}
