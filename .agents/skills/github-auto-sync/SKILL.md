---
name: github-auto-sync
description: Safely initialize, inspect, publish, or automatically synchronize a local code repository with GitHub. Use when the user asks to auto-sync, push, publish or save code to GitHub, initialize a GitHub repository, inspect GitHub sync status, or repair the auto-sync setup. Do not trigger GitHub writes for read-only code questions.
---

# GitHub Auto Sync

Use the `github_repository` MCP tool for repository operations. Prefer `safe_sync` for completed code changes and never substitute an unconditional `git add .` or `git add -A`.

## Workflow

1. At the start of a coding turn, ensure a baseline exists for the current session, turn, and repository root. The lifecycle Hook normally captures it.
2. Complete one coherent code change and run the repository checks configured in `.github-auto-sync.json`.
3. Call `github_repository` with `action: "safe_sync"`, the baseline id, current expected branch, a short conventional commit message, and exact `includePaths` when Codex has a reliable touched-file list.
4. Treat success as verified only when the returned local and remote commit SHAs match.
5. Report the structured status, commit SHA, branch, remote, checks, included paths, and exclusions.

Use conventional commit messages such as `feat: ...`, `fix: ...`, `refactor: ...`, `docs: ...`, `test: ...`, or `chore: ...`. If no reliable semantic summary is available, use `chore: sync Codex changes`.

## Initialization

- Run the installed coordinator at `~/.codex/tools/github-auto-sync/dist/src/cli.js` with Node and `setup --path <repository-root>` for each repository that should auto-sync.
- If the directory is not a Git repository, verify that it is not inside another repository and is not a home, drive-root, or system directory before initializing it.
- If no GitHub repository exists, prepare a private personal repository by default. Before the first real repository creation or upload, show the account, repository, visibility, local root, branch, remote, file count, large-file findings, and sensitive-content findings, then obtain one confirmation.
- Reuse Git Credential Manager, another safe credential helper, `gh`, or an environment credential. Never ask the user to paste a password, PAT, token, SSH private key, or API key into chat.
- Do not invent Git `user.name` or `user.email`; ask only when neither can be determined reliably.

## Stop conditions

Do not commit or push when checks fail; secrets are suspected; baseline changes are ambiguous; pre-existing staged content conflicts; HEAD is detached; a merge, rebase, cherry-pick, revert, bisect, or conflict is active; the requested branch differs from HEAD; the remote changed; or the remote is ahead/diverged.

Never reset, restore, checkout, stash, clean, amend earlier commits, overwrite a remote, pull/rebase automatically, or force-push to make auto-sync succeed. Preserve local work and return the exact error status. If a local commit succeeds but the network or push fails, report `committed locally, push pending` with its SHA.

Use `dry-run`, `status`, `pause`, `resume`, and `doctor` coordinator commands when requested. Use the installed `scripts/install.ps1 -Mode Uninstall -ProjectRoot <repository-root>` for uninstall. A dry run must not modify the index, create a commit, or push.
