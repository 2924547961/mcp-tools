import fs from "node:fs";
import path from "node:path";
import { AutoSyncConfig, BaselineSnapshot, SyncError, SyncResult } from "./auto-sync-types.js";
import {
  currentFileHash,
  parseStatus,
  readBaseline,
  readBaselineResult,
  repositoryRoot,
  writeBaselineResult,
} from "./baseline.js";
import { gitExecutable, isPathInside } from "./config.js";
import { runCommand } from "./process.js";

const DEFAULT_CONFIG: AutoSyncConfig = {
  enabled: true,
  remote: "origin",
  branchPolicy: "current",
  checks: [],
  allowWithoutChecks: false,
  verifyRemote: true,
};

const sensitiveNames = [
  /^\.env(?:\..+)?$/i,
  /\.(?:pem|key|p12|pfx)$/i,
  /^id_(?:rsa|dsa|ecdsa|ed25519)$/i,
  /^credentials.*\.json$/i,
  /service[-_. ]?account.*\.json$/i,
];

const secretPatterns: Array<{ label: string; pattern: RegExp }> = [
  { label: "private key", pattern: /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/ },
  { label: "GitHub token", pattern: /\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b/ },
  { label: "OpenAI API key", pattern: /\bsk-[A-Za-z0-9_-]{20,}\b/ },
  { label: "AWS access key", pattern: /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/ },
  {
    label: "credential assignment",
    pattern: /^\s*["']?(?:password|passwd|secret|private_key|api[_-]?key|access[_-]?token|authorization)["']?\s*[:=]\s*["'`]?(?!example\b|sample\b|placeholder\b|changeme\b|change-me\b|your[_-]|<[^>]+>|\$\{[^}]+\})[A-Za-z0-9/+_-]{10,}/im,
  },
];

async function git(cwd: string, args: string[], allowExitCodes = [0], timeoutMs = 120_000) {
  return runCommand(gitExecutable(), args, { cwd, allowExitCodes, timeoutMs });
}

function configPath(root: string): string {
  return path.join(root, ".github-auto-sync.json");
}

export function readAutoSyncConfig(root: string): AutoSyncConfig {
  const target = configPath(root);
  if (!fs.existsSync(target)) return { ...DEFAULT_CONFIG };
  const input = JSON.parse(fs.readFileSync(target, "utf8")) as Partial<AutoSyncConfig>;
  return {
    enabled: input.enabled ?? DEFAULT_CONFIG.enabled,
    remote: input.remote?.trim() || DEFAULT_CONFIG.remote,
    branchPolicy: "current",
    checks: Array.isArray(input.checks) ? input.checks : [],
    allowWithoutChecks: input.allowWithoutChecks ?? false,
    verifyRemote: input.verifyRemote ?? true,
  };
}

export function writeAutoSyncConfig(root: string, config: AutoSyncConfig): void {
  fs.writeFileSync(configPath(root), `${JSON.stringify(config, null, 2)}\n`);
}

function normalizeRelativePath(root: string, requested: string): string {
  if (!requested || path.isAbsolute(requested)) {
    throw new SyncError("permission_required", `includePaths must be repository-relative: ${requested}`);
  }
  const absolute = path.resolve(root, requested);
  if (!isPathInside(absolute, root)) {
    throw new SyncError("permission_required", `includePath escapes the repository: ${requested}`);
  }
  return path.relative(root, absolute).split(path.sep).join("/");
}

function commandParts(value: string): string[] {
  const parts: string[] = [];
  const pattern = /"((?:\\.|[^"])*)"|'([^']*)'|([^\s]+)/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(value)) !== null) {
    parts.push((match[1] ?? match[2] ?? match[3]).replace(/\\"/g, '"'));
  }
  return parts;
}

async function runChecks(root: string, config: AutoSyncConfig): Promise<SyncResult["checks"]> {
  if (!config.checks.length) {
    if (!config.allowWithoutChecks) {
      throw new SyncError(
        "checks_not_configured",
        "No trusted project checks are configured; automatic synchronization is disabled until a policy is chosen.",
      );
    }
    return "not_configured";
  }
  const results: Array<{ command: string; ok: boolean; output?: string }> = [];
  for (const check of config.checks) {
    const parts = typeof check === "string" ? commandParts(check) : [check.command, ...(check.args ?? [])];
    if (!parts.length || !parts[0]) {
      throw new SyncError("checks_failed", "Invalid empty check command in .github-auto-sync.json");
    }
    const label = parts.map(value => (/\s/.test(value) ? JSON.stringify(value) : value)).join(" ");
    try {
      const result = await runCommand(parts[0], parts.slice(1), { cwd: root, timeoutMs: 600_000 });
      results.push({ command: label, ok: true, output: (result.stdout || result.stderr).trim().slice(-4000) });
    } catch (error) {
      results.push({ command: label, ok: false, output: error instanceof Error ? error.message.slice(-4000) : String(error) });
      throw new SyncError("checks_failed", `Project check failed: ${label}`, { checks: results });
    }
  }
  return results;
}

async function assertRepositoryState(root: string): Promise<string> {
  const branch = (await git(root, ["branch", "--show-current"])).stdout.trim();
  if (!branch) throw new SyncError("detached_head", "Automatic sync is disabled on detached HEAD.");
  const gitDir = path.resolve(root, (await git(root, ["rev-parse", "--git-dir"])).stdout.trim());
  const markers: Array<[string, ConstructorParameters<typeof SyncError>[0]]> = [
    ["MERGE_HEAD", "merge_in_progress"],
    ["rebase-merge", "rebase_in_progress"],
    ["rebase-apply", "rebase_in_progress"],
    ["CHERRY_PICK_HEAD", "cherry_pick_in_progress"],
    ["REVERT_HEAD", "revert_in_progress"],
    ["BISECT_LOG", "bisect_in_progress"],
  ];
  for (const [marker, code] of markers) {
    if (fs.existsSync(path.join(gitDir, marker))) {
      throw new SyncError(code, `Repository operation is in progress: ${marker}`);
    }
  }
  const conflicts = await git(root, ["diff", "--name-only", "--diff-filter=U", "-z"]);
  if (conflicts.stdout) {
    throw new SyncError("unresolved_conflicts", "Repository has unresolved conflicts.");
  }
  return branch;
}

function classifyChanges(
  root: string,
  baseline: BaselineSnapshot,
  status: Array<{ status: string; file: string }>,
  requestedPaths?: string[],
): { included: string[]; excluded: string[] } {
  const baselineMap = new Map(baseline.files.map(file => [file.path.split(path.sep).join("/"), file]));
  const changed = new Map(status.map(entry => [entry.file.split(path.sep).join("/"), entry]));
  const ambiguous: string[] = [];
  const safe: string[] = [];
  const excluded: string[] = [];

  for (const [file, entry] of changed) {
    if (file === ".codex/github-auto-sync" || file.startsWith(".codex/github-auto-sync/")) {
      excluded.push(file);
      continue;
    }
    const before = baselineMap.get(file);
    if (!before) {
      safe.push(file);
      continue;
    }
    const same = before.status === entry.status && before.hash === currentFileHash(root, file);
    if (same) excluded.push(file);
    else ambiguous.push(file);
  }
  for (const file of baselineMap.keys()) {
    if (!changed.has(file)) excluded.push(file);
  }
  if (ambiguous.length) {
    throw new SyncError(
      "ambiguous_changes",
      `ambiguous pre-existing modification: ${ambiguous.join(", ")}`,
      { paths: ambiguous },
    );
  }

  if (!requestedPaths) return { included: [...new Set(safe)].sort(), excluded: [...new Set(excluded)].sort() };
  const requested = [...new Set(requestedPaths.map(value => normalizeRelativePath(root, value)))];
  const unsafe = requested.filter(file => !safe.includes(file));
  if (unsafe.length) {
    throw new SyncError("preexisting_changes", `Requested paths are not safe changes from this baseline: ${unsafe.join(", ")}`);
  }
  return {
    included: requested.sort(),
    excluded: [...new Set([...excluded, ...safe.filter(file => !requested.includes(file))])].sort(),
  };
}

export function scanSensitiveFiles(root: string, files: string[]): void {
  const findings: Array<{ path: string; reason: string }> = [];
  for (const relative of files) {
    const absolute = path.join(root, relative);
    if (!fs.existsSync(absolute)) continue;
    const basename = path.basename(relative);
    const exampleLike = /(?:\.env\.example|\.example|\.sample|sample[-_.]?config|config[-_.]?sample)$/i.test(basename);
    if (!exampleLike && sensitiveNames.some(pattern => pattern.test(basename))) {
      findings.push({ path: relative, reason: "sensitive filename" });
      continue;
    }
    const stat = fs.statSync(absolute);
    if (!stat.isFile()) continue;
    if (stat.size > 100 * 1024 * 1024) {
      findings.push({ path: relative, reason: "file exceeds 100 MiB" });
      continue;
    }
    const buffer = fs.readFileSync(absolute);
    if (buffer.includes(0)) continue;
    const content = buffer.toString("utf8");
    for (const candidate of secretPatterns) {
      if (candidate.pattern.test(content)) {
        findings.push({ path: relative, reason: candidate.label });
        break;
      }
    }
  }
  if (findings.length) {
    throw new SyncError("sensitive_content", "Refusing to commit files that may contain credentials.", { findings });
  }
}

function validateRemoteUrl(url: string): string {
  const github = url.match(/^(?:https:\/\/github\.com\/|git@github\.com:)([^/\s:]+)\/([^/\s]+?)(?:\.git)?$/i);
  if (github) return `${github[1]}/${github[2].replace(/\.git$/i, "")}`;
  if (process.env.GITHUB_MCP_ALLOW_LOCAL_REMOTES_FOR_TESTS === "1" && (/^(?:file:\/\/)/i.test(url) || path.isAbsolute(url))) {
    return url;
  }
  throw new SyncError("remote_invalid", `Automatic sync only accepts an existing github.com remote: ${url}`);
}

async function remotePreflight(root: string, remote: string, branch: string): Promise<{
  repository: string;
  remoteUrl: string;
  remoteCommit: string | null;
  reachable: boolean;
  message?: string;
}> {
  const remoteResult = await git(root, ["remote", "get-url", remote], [0, 2]);
  const remoteUrl = remoteResult.stdout.trim();
  if (!remoteUrl) throw new SyncError("remote_invalid", `Remote does not exist: ${remote}`);
  const repository = validateRemoteUrl(remoteUrl);

  const upstream = await git(root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], [0, 128]);
  if (upstream.code === 0) {
    const configured = upstream.stdout.trim();
    if (!configured.startsWith(`${remote}/`)) {
      throw new SyncError("remote_mismatch", `Current branch upstream is ${configured}, not ${remote}/${branch}.`);
    }
    if (configured !== `${remote}/${branch}`) {
      throw new SyncError("remote_mismatch", `Current branch upstream is ${configured}, not ${remote}/${branch}.`);
    }
  }

  let listing;
  try {
    listing = await git(root, ["ls-remote", "--heads", remote, `refs/heads/${branch}`], [0], 60_000);
  } catch (error) {
    return { repository, remoteUrl, remoteCommit: null, reachable: false, message: error instanceof Error ? error.message : String(error) };
  }
  const remoteCommit = listing.stdout.trim().split(/\s+/)[0] || null;
  if (!remoteCommit) return { repository, remoteUrl, remoteCommit: null, reachable: true };
  await git(root, ["fetch", "--no-tags", remote, `refs/heads/${branch}`], [0], 120_000);
  const localHead = (await git(root, ["rev-parse", "HEAD"])).stdout.trim();
  const remoteIsAncestor = await git(root, ["merge-base", "--is-ancestor", remoteCommit, localHead], [0, 1]);
  if (remoteIsAncestor.code === 0) return { repository, remoteUrl, remoteCommit, reachable: true };
  const localIsAncestor = await git(root, ["merge-base", "--is-ancestor", localHead, remoteCommit], [0, 1]);
  if (localIsAncestor.code === 0) {
    throw new SyncError("remote_ahead", `Remote ${remote}/${branch} is ahead of local HEAD.`);
  }
  throw new SyncError("remote_diverged", `Local ${branch} and ${remote}/${branch} have diverged.`);
}

async function ensureIdentity(root: string): Promise<void> {
  const [name, email] = await Promise.all([
    git(root, ["config", "user.name"], [0, 1]),
    git(root, ["config", "user.email"], [0, 1]),
  ]);
  if (!name.stdout.trim() || !email.stdout.trim()) {
    throw new SyncError(
      "environment_missing",
      "Git identity is missing. Configure repository user.name and user.email; Codex will not invent them.",
    );
  }
}

function emptyResult(root: string, branch: string | null, remote: string | null): SyncResult {
  return {
    status: "no_changes",
    localPath: root,
    repository: null,
    remote,
    branch,
    commit: null,
    remoteCommit: null,
    committed: false,
    pushed: false,
    verified: false,
    noChanges: true,
    includedPaths: [],
    excludedPaths: [],
    checks: "not_configured",
  };
}

export async function safeSync(input: {
  localPath: string;
  baselineId: string;
  expectedBranch?: string;
  remoteName?: string;
  includePaths?: string[];
  commitMessage?: string;
  runChecks?: boolean;
  verifyRemote?: boolean;
  dryRun?: boolean;
}): Promise<SyncResult> {
  const root = await repositoryRoot(input.localPath);
  const already = readBaselineResult(root, input.baselineId);
  if (already) return already as SyncResult;
  const baseline = readBaseline(root, input.baselineId);
  const config = readAutoSyncConfig(root);
  const branch = await assertRepositoryState(root);
  const remote = input.remoteName || config.remote;
  if (!config.enabled) {
    return { ...emptyResult(root, branch, remote), message: "Automatic synchronization is paused." };
  }
  if (input.expectedBranch && input.expectedBranch !== branch) {
    throw new SyncError("branch_mismatch", `Current branch ${branch} does not match requested branch ${input.expectedBranch}.`);
  }
  if (baseline.branch !== branch) {
    throw new SyncError("branch_mismatch", `Branch changed since baseline: ${baseline.branch ?? "detached"} -> ${branch}.`);
  }
  if (baseline.files.some(file => file.staged)) {
    throw new SyncError("staged_changes_conflict", "Baseline contains pre-existing staged changes.");
  }

  const lockName = `github-auto-sync-${branch.replace(/[^A-Za-z0-9._-]/g, "_")}.lock`;
  const lockPath = path.join(baseline.gitCommonDir, lockName);
  try {
    fs.mkdirSync(lockPath);
  } catch (error) {
    const nodeError = error as NodeJS.ErrnoException;
    if (nodeError.code === "EEXIST") {
      throw new SyncError("permission_required", `Another auto-sync is already running for branch ${branch}.`);
    }
    throw error;
  }

  try {
    const statusResult = await git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]);
    const classified = classifyChanges(root, baseline, parseStatus(statusResult.stdout), input.includePaths);
    if (!classified.included.length) {
      const result = { ...emptyResult(root, branch, remote), excludedPaths: classified.excluded };
      writeBaselineResult(root, input.baselineId, result);
      return result;
    }

    const currentStaged = (await git(root, ["diff", "--cached", "--name-only", "-z"])).stdout.split("\0").filter(Boolean);
    const stagedOutsideScope = currentStaged.filter(file => !classified.included.includes(file.split(path.sep).join("/")));
    if (stagedOutsideScope.length) {
      throw new SyncError("staged_changes_conflict", `Staged changes are outside this sync scope: ${stagedOutsideScope.join(", ")}`);
    }

    scanSensitiveFiles(root, classified.included);
    const checks = input.runChecks === false ? "not_configured" : await runChecks(root, config);
    const baselineRemote = baseline.remotes?.[remote];
    const currentRemote = (await git(root, ["remote", "get-url", remote], [0, 2])).stdout.trim();
    if (baselineRemote && currentRemote && baselineRemote !== currentRemote) {
      throw new SyncError("remote_mismatch", `Remote ${remote} changed since baseline.`);
    }
    const currentUpstream = await git(root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], [0, 128]);
    if (baseline.upstream && currentUpstream.stdout.trim() !== baseline.upstream) {
      throw new SyncError("remote_mismatch", "Branch upstream changed since baseline.");
    }
    const preflight = await remotePreflight(root, remote, branch);
    if (input.dryRun) {
      return {
        status: "success",
        localPath: root,
        repository: preflight.repository,
        remote,
        branch,
        commit: null,
        remoteCommit: preflight.remoteCommit,
        committed: false,
        pushed: false,
        verified: false,
        noChanges: false,
        includedPaths: classified.included,
        excludedPaths: classified.excluded,
        checks,
        message: "Dry run only; index, commits, and remote were not modified.",
      };
    }

    await ensureIdentity(root);
    await git(root, ["add", "--", ...classified.included]);
    const staged = (await git(root, ["diff", "--cached", "--name-only", "-z"])).stdout.split("\0").filter(Boolean);
    const unexpected = staged.filter(file => !classified.included.includes(file.split(path.sep).join("/")));
    if (unexpected.length) {
      throw new SyncError("staged_changes_conflict", `Unexpected staged paths after exact staging: ${unexpected.join(", ")}`);
    }
    await git(root, ["diff", "--cached", "--check"]);
    const hasChanges = await git(root, ["diff", "--cached", "--quiet"], [0, 1]);
    if (hasChanges.code === 0) {
      const result = { ...emptyResult(root, branch, remote), excludedPaths: classified.excluded };
      writeBaselineResult(root, input.baselineId, result);
      return result;
    }
    await git(root, ["commit", "-m", input.commitMessage?.trim() || "chore: sync Codex changes"]);
    const commit = (await git(root, ["rev-parse", "HEAD"])).stdout.trim();

    if (!preflight.reachable) {
      const result: SyncResult = {
        status: "push_pending",
        localPath: root,
        repository: preflight.repository,
        remote,
        branch,
        commit,
        remoteCommit: null,
        committed: true,
        pushed: false,
        verified: false,
        noChanges: false,
        includedPaths: classified.included,
        excludedPaths: classified.excluded,
        checks,
        message: `committed locally, push pending: ${preflight.message}`,
      };
      writeBaselineResult(root, input.baselineId, result);
      return result;
    }

    try {
      await git(root, ["push", "-u", remote, `HEAD:refs/heads/${branch}`], [0], 180_000);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const code = /auth|credential|permission denied|403|could not read username/i.test(message)
        ? "authentication_required"
        : "push_failed";
      const result: SyncResult = {
        status: code,
        localPath: root,
        repository: preflight.repository,
        remote,
        branch,
        commit,
        remoteCommit: preflight.remoteCommit,
        committed: true,
        pushed: false,
        verified: false,
        noChanges: false,
        includedPaths: classified.included,
        excludedPaths: classified.excluded,
        checks,
        message: `committed locally, push pending: ${message}`,
      };
      writeBaselineResult(root, input.baselineId, result);
      return result;
    }

    const verify = await git(root, ["ls-remote", "--heads", remote, `refs/heads/${branch}`], [0], 60_000);
    const remoteCommit = verify.stdout.trim().split(/\s+/)[0] || null;
    const verified = remoteCommit === commit;
    const result: SyncResult = {
      status: verified || input.verifyRemote === false || config.verifyRemote === false ? "success" : "remote_verification_failed",
      localPath: root,
      repository: preflight.repository,
      remote,
      branch,
      commit,
      remoteCommit,
      committed: true,
      pushed: true,
      verified,
      noChanges: false,
      includedPaths: classified.included,
      excludedPaths: classified.excluded,
      checks,
      ...(!verified ? { message: "Push returned success, but the remote branch SHA did not match local HEAD." } : {}),
    };
    writeBaselineResult(root, input.baselineId, result);
    return result;
  } finally {
    fs.rmSync(lockPath, { recursive: true, force: true });
  }
}

export async function captureBaseline(input: { localPath: string; sessionId: string; turnId: string }) {
  const { snapshotWorkingTree } = await import("./baseline.js");
  return snapshotWorkingTree(input.localPath, input.sessionId, input.turnId);
}

export { DEFAULT_CONFIG };
