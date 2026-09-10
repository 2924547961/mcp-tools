export type SyncErrorCode =
  | "environment_missing"
  | "authentication_required"
  | "permission_required"
  | "hook_trust_required"
  | "checks_failed"
  | "checks_not_configured"
  | "sensitive_content"
  | "preexisting_changes"
  | "ambiguous_changes"
  | "staged_changes_conflict"
  | "remote_ahead"
  | "remote_diverged"
  | "merge_in_progress"
  | "rebase_in_progress"
  | "cherry_pick_in_progress"
  | "revert_in_progress"
  | "bisect_in_progress"
  | "unresolved_conflicts"
  | "detached_head"
  | "branch_mismatch"
  | "remote_invalid"
  | "remote_mismatch"
  | "push_failed"
  | "push_pending"
  | "remote_verification_failed"
  | "success"
  | "no_changes";

export class SyncError extends Error {
  constructor(
    public readonly code: SyncErrorCode,
    message: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "SyncError";
  }
}

export interface FileSnapshot {
  path: string;
  status: string;
  hash: string | null;
  staged: boolean;
  untracked: boolean;
}

export interface BaselineSnapshot {
  version: 1;
  id: string;
  sessionId: string;
  turnId: string;
  repositoryRoot: string;
  gitCommonDir: string;
  head: string | null;
  branch: string | null;
  upstream: string | null;
  remotes: Record<string, string>;
  createdAt: string;
  files: FileSnapshot[];
}

export interface AutoSyncConfig {
  enabled: boolean;
  remote: string;
  branchPolicy: "current";
  checks: Array<string | { command: string; args?: string[] }>;
  allowWithoutChecks: boolean;
  verifyRemote: boolean;
}

export interface SyncResult {
  status: SyncErrorCode;
  localPath: string;
  repository: string | null;
  remote: string | null;
  branch: string | null;
  commit: string | null;
  remoteCommit: string | null;
  committed: boolean;
  pushed: boolean;
  verified: boolean;
  noChanges: boolean;
  includedPaths: string[];
  excludedPaths: string[];
  checks: Array<{ command: string; ok: boolean; output?: string }> | "not_configured";
  message?: string;
}
