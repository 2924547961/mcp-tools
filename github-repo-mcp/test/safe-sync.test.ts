import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { baselineId, snapshotWorkingTree } from "../src/baseline.js";
import { SyncError } from "../src/auto-sync-types.js";
import { safeSync } from "../src/safe-sync.js";
import { syncChanges } from "../src/git.js";

process.env.GITHUB_MCP_ALLOWED_ROOTS = os.tmpdir();
process.env.GITHUB_MCP_ALLOW_LOCAL_REMOTES_FOR_TESTS = "1";

function git(cwd: string, args: string[], allowFailure = false): string {
  try {
    return execFileSync("git", args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
  } catch (error) {
    if (allowFailure) return "";
    throw error;
  }
}

interface Fixture { base: string; repo: string; remote: string }

function fixture(name = "project"): Fixture {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "github-auto-sync-test-"));
  const repo = path.join(base, name);
  const remote = path.join(base, "remote.git");
  fs.mkdirSync(repo, { recursive: true });
  git(repo, ["init", "-b", "main"]);
  git(repo, ["config", "user.name", "Test User"]);
  git(repo, ["config", "user.email", "test@example.invalid"]);
  fs.writeFileSync(path.join(repo, "tracked.txt"), "initial\n");
  git(repo, ["add", "--", "tracked.txt"]);
  git(repo, ["commit", "-m", "initial"]);
  git(base, ["init", "--bare", remote]);
  git(repo, ["remote", "add", "origin", remote]);
  git(repo, ["push", "-u", "origin", "main"]);
  git(base, ["--git-dir", remote, "symbolic-ref", "HEAD", "refs/heads/main"]);
  fs.writeFileSync(path.join(repo, ".github-auto-sync.json"), JSON.stringify({
    enabled: true,
    remote: "origin",
    branchPolicy: "current",
    checks: [],
    allowWithoutChecks: true,
    verifyRemote: true,
  }));
  return { base, repo, remote };
}

function cleanup(value: Fixture): void {
  fs.rmSync(value.base, { recursive: true, force: true });
}

async function baseline(value: Fixture, turn = "turn") {
  return snapshotWorkingTree(value.repo, "session", turn);
}

async function expectCode(promise: Promise<unknown>, code: string): Promise<void> {
  await assert.rejects(promise, error => error instanceof SyncError && error.code === code);
}

test("1 ordinary tracked modification is committed, pushed, and verified", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "changed\n");
    const result = await safeSync({ localPath: value.repo, baselineId: before.id });
    assert.equal(result.verified, true); assert.equal(result.includedPaths[0], "tracked.txt");
  } finally { cleanup(value); }
});

test("2 new file is included exactly", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.writeFileSync(path.join(value.repo, "new.txt"), "new\n");
    const result = await safeSync({ localPath: value.repo, baselineId: before.id });
    assert.deepEqual(result.includedPaths, ["new.txt"]);
  } finally { cleanup(value); }
});

test("3 deleted file is included exactly", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.unlinkSync(path.join(value.repo, "tracked.txt"));
    const result = await safeSync({ localPath: value.repo, baselineId: before.id });
    assert.deepEqual(result.includedPaths, ["tracked.txt"]);
  } finally { cleanup(value); }
});

test("4 no changes creates no commit", async () => {
  const value = fixture(); try {
    const before = await baseline(value); const head = git(value.repo, ["rev-parse", "HEAD"]);
    const result = await safeSync({ localPath: value.repo, baselineId: before.id });
    assert.equal(result.noChanges, true); assert.equal(git(value.repo, ["rev-parse", "HEAD"]), head);
  } finally { cleanup(value); }
});

test("5 untouched pre-existing unstaged modification is excluded", async () => {
  const value = fixture(); try {
    fs.appendFileSync(path.join(value.repo, "tracked.txt"), "user\n"); const before = await baseline(value);
    fs.writeFileSync(path.join(value.repo, "codex.txt"), "codex\n");
    const result = await safeSync({ localPath: value.repo, baselineId: before.id });
    assert.deepEqual(result.includedPaths, ["codex.txt"]); assert.match(fs.readFileSync(path.join(value.repo, "tracked.txt"), "utf8"), /user/);
  } finally { cleanup(value); }
});

test("6 touched pre-existing unstaged modification is ambiguous", async () => {
  const value = fixture(); try {
    fs.appendFileSync(path.join(value.repo, "tracked.txt"), "user\n"); const before = await baseline(value);
    fs.appendFileSync(path.join(value.repo, "tracked.txt"), "codex\n");
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "ambiguous_changes");
  } finally { cleanup(value); }
});

test("7 pre-existing staged content blocks synchronization", async () => {
  const value = fixture(); try {
    fs.appendFileSync(path.join(value.repo, "tracked.txt"), "user\n"); git(value.repo, ["add", "--", "tracked.txt"]); const before = await baseline(value);
    fs.writeFileSync(path.join(value.repo, "codex.txt"), "codex\n");
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "staged_changes_conflict");
  } finally { cleanup(value); }
});

test("8 includePaths can select a new file", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.writeFileSync(path.join(value.repo, "a.txt"), "a"); fs.writeFileSync(path.join(value.repo, "b.txt"), "b");
    const result = await safeSync({ localPath: value.repo, baselineId: before.id, includePaths: ["a.txt"] });
    assert.deepEqual(result.includedPaths, ["a.txt"]); assert.equal(fs.existsSync(path.join(value.repo, "b.txt")), true);
  } finally { cleanup(value); }
});

test("9 .env is rejected", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.writeFileSync(path.join(value.repo, ".env"), "SAFE=no\n");
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "sensitive_content");
  } finally { cleanup(value); }
});

test("10 tracked .env modification is rejected", async () => {
  const value = fixture(); try {
    fs.writeFileSync(path.join(value.repo, ".env"), "A=placeholder\n"); git(value.repo, ["add", "--", ".env"]); git(value.repo, ["commit", "-m", "env"]); git(value.repo, ["push"]);
    const before = await baseline(value); fs.appendFileSync(path.join(value.repo, ".env"), "B=value\n");
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "sensitive_content");
  } finally { cleanup(value); }
});

test("11 .env.example placeholder is allowed", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.writeFileSync(path.join(value.repo, ".env.example"), "API_KEY=your_api_key\n");
    const result = await safeSync({ localPath: value.repo, baselineId: before.id }); assert.equal(result.verified, true);
  } finally { cleanup(value); }
});

test("12 .env.example real-looking token is rejected", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.writeFileSync(path.join(value.repo, ".env.example"), `OPENAI_API_KEY=sk-${"a".repeat(32)}\n`);
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "sensitive_content");
  } finally { cleanup(value); }
});

test("13 PEM private key is rejected", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.writeFileSync(path.join(value.repo, "server.pem"), ["-----BEGIN", "PRIVATE KEY-----", "abc"].join(" ") + "\n");
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "sensitive_content");
  } finally { cleanup(value); }
});

test("14 Chinese filename is synchronized", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.writeFileSync(path.join(value.repo, "中文文件.txt"), "ok\n");
    const result = await safeSync({ localPath: value.repo, baselineId: before.id }); assert.deepEqual(result.includedPaths, ["中文文件.txt"]);
  } finally { cleanup(value); }
});

test("15 repository path containing spaces is synchronized", async () => {
  const value = fixture("space project"); try {
    const before = await baseline(value); fs.writeFileSync(path.join(value.repo, "new file.txt"), "ok\n");
    const result = await safeSync({ localPath: value.repo, baselineId: before.id }); assert.equal(result.verified, true);
  } finally { cleanup(value); }
});

test("16 detached HEAD is rejected", async () => {
  const value = fixture(); try {
    const before = await baseline(value); git(value.repo, ["checkout", "--detach"]); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x");
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "detached_head");
  } finally { cleanup(value); }
});

test("17 merge conflict is rejected", async () => {
  const value = fixture(); try {
    const before = await baseline(value); git(value.repo, ["checkout", "-b", "other"]); fs.writeFileSync(path.join(value.repo, "tracked.txt"), "other\n"); git(value.repo, ["commit", "-am", "other"]);
    git(value.repo, ["checkout", "main"]); fs.writeFileSync(path.join(value.repo, "tracked.txt"), "main\n"); git(value.repo, ["commit", "-am", "main"]); git(value.repo, ["merge", "other"], true);
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "merge_in_progress");
  } finally { cleanup(value); }
});

test("18 merge in progress marker is rejected", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.writeFileSync(path.join(value.repo, ".git", "MERGE_HEAD"), git(value.repo, ["rev-parse", "HEAD"]));
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "merge_in_progress");
  } finally { cleanup(value); }
});

test("19 rebase in progress marker is rejected", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.mkdirSync(path.join(value.repo, ".git", "rebase-merge"));
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "rebase_in_progress");
  } finally { cleanup(value); }
});

test("20 remote ahead is rejected", async () => {
  const value = fixture(); try {
    const before = await baseline(value); const clone = path.join(value.base, "clone"); git(value.base, ["clone", value.remote, clone]); git(clone, ["config", "user.name", "Other"]); git(clone, ["config", "user.email", "other@example.invalid"]);
    fs.writeFileSync(path.join(clone, "remote.txt"), "remote"); git(clone, ["add", "--", "remote.txt"]); git(clone, ["commit", "-m", "remote"]); git(clone, ["push"]);
    fs.appendFileSync(path.join(value.repo, "tracked.txt"), "local\n"); await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "remote_ahead");
  } finally { cleanup(value); }
});

test("21 diverged history is rejected", async () => {
  const value = fixture(); try {
    fs.writeFileSync(path.join(value.repo, "local-base.txt"), "local"); git(value.repo, ["add", "--", "local-base.txt"]); git(value.repo, ["commit", "-m", "local only"]);
    const clone = path.join(value.base, "clone"); git(value.base, ["clone", value.remote, clone]); git(clone, ["config", "user.name", "Other"]); git(clone, ["config", "user.email", "other@example.invalid"]); fs.writeFileSync(path.join(clone, "remote.txt"), "remote"); git(clone, ["add", "--", "remote.txt"]); git(clone, ["commit", "-m", "remote"]); git(clone, ["push"]);
    const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "change\n"); await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "remote_diverged");
  } finally { cleanup(value); }
});

test("22 unreachable remote preserves a local commit as push pending", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "local\n"); fs.rmSync(value.remote, { recursive: true, force: true });
    const result = await safeSync({ localPath: value.repo, baselineId: before.id }); assert.equal(result.status, "push_pending"); assert.equal(result.committed, true);
  } finally { cleanup(value); }
});

test("23 rejected push preserves the local commit", async () => {
  const value = fixture(); try {
    const hookDir = path.join(value.remote, "hooks"); const hook = path.join(hookDir, "pre-receive"); fs.writeFileSync(hook, "#!/bin/sh\nexit 1\n"); fs.chmodSync(hook, 0o755);
    const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "local\n");
    const result = await safeSync({ localPath: value.repo, baselineId: before.id }); assert.equal(result.status, "push_failed"); assert.equal(result.committed, true);
  } finally { cleanup(value); }
});

test("24 duplicate Stop returns the saved result without another commit", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n"); const first = await safeSync({ localPath: value.repo, baselineId: before.id });
    const second = await safeSync({ localPath: value.repo, baselineId: before.id }); assert.equal(second.commit, first.commit); assert.equal(git(value.repo, ["rev-list", "--count", "HEAD"]), "2");
  } finally { cleanup(value); }
});

test("25 concurrent session lock blocks a second sync", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n"); const common = path.resolve(value.repo, git(value.repo, ["rev-parse", "--git-common-dir"])); fs.mkdirSync(path.join(common, "github-auto-sync-main.lock"));
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "permission_required");
  } finally { cleanup(value); }
});

test("26 Git worktree uses the shared common-dir lock and syncs", async () => {
  const value = fixture(); try {
    const worktree = path.join(value.base, "work tree"); git(value.repo, ["worktree", "add", "-b", "feature", worktree]); fs.writeFileSync(path.join(worktree, ".github-auto-sync.json"), fs.readFileSync(path.join(value.repo, ".github-auto-sync.json")));
    const before = await snapshotWorkingTree(worktree, "session", "worktree"); fs.appendFileSync(path.join(worktree, "tracked.txt"), "feature\n"); const result = await safeSync({ localPath: worktree, baselineId: before.id }); assert.equal(result.verified, true);
  } finally { cleanup(value); }
});

test("27 requested branch mismatch is rejected", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n"); await expectCode(safeSync({ localPath: value.repo, baselineId: before.id, expectedBranch: "other" }), "branch_mismatch");
  } finally { cleanup(value); }
});

test("28 origin changed after baseline is rejected", async () => {
  const value = fixture(); try {
    const before = await baseline(value); const other = path.join(value.base, "other.git"); git(value.base, ["init", "--bare", other]); git(value.repo, ["remote", "set-url", "origin", other]); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n");
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "remote_mismatch");
  } finally { cleanup(value); }
});

test("29 dry-run does not modify index, HEAD, or remote", async () => {
  const value = fixture(); try {
    const before = await baseline(value); const head = git(value.repo, ["rev-parse", "HEAD"]); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n"); const result = await safeSync({ localPath: value.repo, baselineId: before.id, dryRun: true });
    assert.equal(result.committed, false); assert.equal(git(value.repo, ["rev-parse", "HEAD"]), head); assert.equal(git(value.repo, ["diff", "--cached", "--name-only"]), "");
  } finally { cleanup(value); }
});

test("30 remote SHA verification matches local HEAD", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n"); const result = await safeSync({ localPath: value.repo, baselineId: before.id });
    assert.equal(result.commit, result.remoteCommit); assert.equal(result.verified, true);
  } finally { cleanup(value); }
});

test("31 missing check policy blocks automatic sync", async () => {
  const value = fixture(); try {
    fs.writeFileSync(path.join(value.repo, ".github-auto-sync.json"), JSON.stringify({ enabled: true, remote: "origin", checks: [], allowWithoutChecks: false })); const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n");
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "checks_not_configured");
  } finally { cleanup(value); }
});

test("32 failed configured check blocks commit", async () => {
  const value = fixture(); try {
    fs.writeFileSync(path.join(value.repo, ".github-auto-sync.json"), JSON.stringify({ enabled: true, remote: "origin", checks: [{ command: process.execPath, args: ["-e", "process.exit(1)"] }] })); const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n");
    await expectCode(safeSync({ localPath: value.repo, baselineId: before.id }), "checks_failed");
  } finally { cleanup(value); }
});

test("33 paused config performs no synchronization", async () => {
  const value = fixture(); try {
    fs.writeFileSync(path.join(value.repo, ".github-auto-sync.json"), JSON.stringify({ enabled: false, remote: "origin", checks: [], allowWithoutChecks: true })); const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n"); const result = await safeSync({ localPath: value.repo, baselineId: before.id }); assert.match(result.message || "", /paused/);
  } finally { cleanup(value); }
});

test("34 includePaths cannot escape repository root", async () => {
  const value = fixture(); try {
    const before = await baseline(value); fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n"); await expectCode(safeSync({ localPath: value.repo, baselineId: before.id, includePaths: ["../outside"] }), "permission_required");
  } finally { cleanup(value); }
});

test("35 baseline id is stable for session and turn", () => {
  assert.equal(baselineId("session/a", "turn:b"), "session_a--turn_b");
});

test("36 legacy sync rejects a requested branch different from HEAD", async () => {
  const value = fixture(); try {
    fs.appendFileSync(path.join(value.repo, "tracked.txt"), "x\n");
    await expectCode(syncChanges({ localPath: value.repo, branch: "other", includePaths: ["tracked.txt"] }), "branch_mismatch");
  } finally { cleanup(value); }
});

test("37 legacy sync scans tracked sensitive files", async () => {
  const value = fixture(); try {
    fs.writeFileSync(path.join(value.repo, ".env"), "TOKEN=placeholder\n"); git(value.repo, ["add", "--", ".env"]); git(value.repo, ["commit", "-m", "env"]); git(value.repo, ["push"]);
    fs.writeFileSync(path.join(value.repo, ".env"), `TOKEN=${["real", "secret", "value", "123456"].join("-")}\n`);
    await expectCode(syncChanges({ localPath: value.repo, includePaths: [".env"] }), "sensitive_content");
  } finally { cleanup(value); }
});
