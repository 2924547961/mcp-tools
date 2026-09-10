import { gitExecutable } from "./config.js";
import { runCommand } from "./process.js";

export interface RepositoryInfo {
  owner: string;
  name: string;
  fullName: string;
  private: boolean;
  defaultBranch: string;
  cloneUrl: string;
  sshUrl: string;
  htmlUrl: string;
}

interface GitHubRepositoryResponse {
  name: string;
  full_name: string;
  private: boolean;
  default_branch: string;
  clone_url: string;
  ssh_url: string;
  html_url: string;
  owner: { login: string };
}

function apiBase(): string {
  const value = (process.env.GITHUB_API_URL || "https://api.github.com").replace(/\/$/, "");
  if (value !== "https://api.github.com") {
    throw new Error("GitHub Enterprise is not supported by this release; GITHUB_API_URL must be https://api.github.com.");
  }
  return value;
}

async function credentialToken(): Promise<string> {
  if (process.env.GITHUB_TOKEN?.trim()) {
    return process.env.GITHUB_TOKEN.trim();
  }
  if (process.env.GH_TOKEN?.trim()) {
    return process.env.GH_TOKEN.trim();
  }

  const credential = await runCommand(gitExecutable(), ["credential", "fill"], {
    input: "protocol=https\nhost=github.com\n\n",
    timeoutMs: 30_000,
  });
  const password = credential.stdout
    .split(/\r?\n/)
    .find(line => line.startsWith("password="))
    ?.slice("password=".length);
  if (!password) {
    throw new Error(
      "GitHub authentication is unavailable. Set GITHUB_TOKEN or sign in through Git Credential Manager.",
    );
  }
  return password;
}

async function githubRequest<T>(pathname: string, init: RequestInit = {}): Promise<T> {
  const token = await credentialToken();
  const response = await fetch(`${apiBase()}${pathname}`, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "github-repo-mcp/0.3.0",
      ...(init.headers ?? {}),
    },
  });

  const text = await response.text();
  if (!response.ok) {
    let message = text;
    try {
      message = (JSON.parse(text) as { message?: string }).message || text;
    } catch {
      // Keep the raw response body.
    }
    throw new Error(`GitHub API ${response.status}: ${message}`);
  }
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

function normalize(response: GitHubRepositoryResponse): RepositoryInfo {
  return {
    owner: response.owner.login,
    name: response.name,
    fullName: response.full_name,
    private: response.private,
    defaultBranch: response.default_branch,
    cloneUrl: response.clone_url,
    sshUrl: response.ssh_url,
    htmlUrl: response.html_url,
  };
}

export async function authenticatedLogin(): Promise<string> {
  const user = await githubRequest<{ login: string }>("/user");
  return user.login;
}

export async function createRepository(input: {
  name: string;
  owner?: string;
  description?: string;
  private?: boolean;
}): Promise<RepositoryInfo> {
  if (!/^[A-Za-z0-9._-]+$/.test(input.name)) {
    throw new Error("Repository name may contain only letters, numbers, dots, underscores, and hyphens.");
  }

  const login = await authenticatedLogin();
  const owner = input.owner?.trim() || login;
  const endpoint = owner.toLowerCase() === login.toLowerCase()
    ? "/user/repos"
    : `/orgs/${encodeURIComponent(owner)}/repos`;
  const response = await githubRequest<GitHubRepositoryResponse>(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: input.name,
      description: input.description ?? "",
      private: input.private ?? true,
      auto_init: false,
    }),
  });
  return normalize(response);
}

export function parseRepositoryReference(reference: string): { owner: string; name: string } {
  const trimmed = reference.trim().replace(/\.git$/, "");
  const ssh = trimmed.match(/^git@github\.com:([^/]+)\/(.+)$/i);
  if (ssh) {
    return { owner: ssh[1], name: ssh[2] };
  }
  const https = trimmed.match(/^https?:\/\/github\.com\/([^/]+)\/([^/]+)$/i);
  if (https) {
    return { owner: https[1], name: https[2] };
  }
  const short = trimmed.match(/^([^/]+)\/([^/]+)$/);
  if (short) {
    return { owner: short[1], name: short[2] };
  }
  throw new Error(`Invalid GitHub repository reference: ${reference}`);
}

export function cloneUrlFor(reference: string): string {
  const parsed = parseRepositoryReference(reference);
  return `https://github.com/${parsed.owner}/${parsed.name}.git`;
}
