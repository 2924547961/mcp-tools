#!/usr/bin/env node

import path from "node:path";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { assertAllowedPath } from "./config.js";
import { createRepository } from "./github.js";
import {
  cloneRepository,
  publishCode,
  pullRepository,
  repositoryStatus,
  syncChanges,
  userFacingError,
} from "./git.js";

const server = new McpServer({
  name: "github-repo-mcp",
  version: "0.2.2",
});

function textResult(data: unknown) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }],
  };
}

function errorResult(error: unknown) {
  return {
    isError: true,
    content: [{ type: "text" as const, text: userFacingError(error) }],
  };
}

const repositoryName = z.string().min(1).max(100).describe("GitHub repository name");
const localPath = z.string().min(1).describe("Absolute local project path");
const repositoryReference = z.string().min(3).describe("owner/name, HTTPS URL, or SSH URL");
const optionalBranch = z.string().min(1).optional().describe("Git branch; defaults to main or current branch");
const remoteName = z.string().min(1).default("origin").describe("Git remote name");

const actionSchema = z.discriminatedUnion("action", [
  z.object({
    action: z.literal("create").describe("Create an empty GitHub repository"),
    name: repositoryName,
    owner: z.string().optional().describe("User or organization; defaults to the authenticated user"),
    description: z.string().max(350).optional(),
    private: z.boolean().default(true),
  }),
  z.object({
    action: z.literal("create_and_publish").describe("After Codex creates code, automatically create a GitHub repository, initialize Git if needed, commit the local project, set origin, and push in one call"),
    localPath,
    name: repositoryName.optional().describe("Defaults to the local directory name"),
    owner: z.string().optional(),
    description: z.string().max(350).optional(),
    private: z.boolean().default(true),
    branch: z.string().min(1).default("main"),
    remoteName,
    commitMessage: z.string().min(1).default("chore: publish repository"),
    includePaths: z.array(z.string().min(1)).optional(),
    allowSensitiveFiles: z.boolean().default(false),
  }),
  z.object({
    action: z.literal("publish").describe("Publish a local directory to an existing GitHub repository"),
    localPath,
    repository: repositoryReference,
    branch: optionalBranch,
    remoteName,
    commitMessage: z.string().min(1).default("chore: publish repository"),
    includePaths: z.array(z.string().min(1)).optional(),
    allowSensitiveFiles: z.boolean().default(false),
  }),
  z.object({
    action: z.literal("sync").describe("Commit and push local code changes"),
    localPath,
    branch: optionalBranch,
    remoteName,
    commitMessage: z.string().min(1).default("chore: sync code changes"),
    includePaths: z.array(z.string().min(1)).optional(),
    includeUntracked: z.boolean().default(false),
    allowSensitiveFiles: z.boolean().default(false),
  }),
  z.object({
    action: z.literal("pull").describe("Pull remote updates into a local repository"),
    localPath,
    branch: optionalBranch,
    remoteName,
    ffOnly: z.boolean().default(true),
  }),
  z.object({
    action: z.literal("clone").describe("Clone a GitHub repository"),
    repository: repositoryReference,
    targetPath: z.string().min(1).describe("Absolute target path under an allowed root"),
    branch: optionalBranch,
    depth: z.number().int().positive().max(1000).optional(),
  }),
  z.object({
    action: z.literal("status").describe("Inspect local repository status"),
    localPath,
  }),
]);

async function createAndPublish(input: Extract<z.infer<typeof actionSchema>, { action: "create_and_publish" }>) {
  const resolved = assertAllowedPath(input.localPath);
  const status = await repositoryStatus(resolved);
  if (status.origin) {
    throw new Error(
      `Local repository already has origin ${status.origin}. Use action=publish or action=sync instead.`,
    );
  }

  const derived = path.basename(resolved).replace(/[^A-Za-z0-9._-]+/g, "-");
  const repository = await createRepository({
    name: input.name || derived,
    owner: input.owner,
    description: input.description,
    private: input.private,
  });

  try {
    const published = await publishCode({
      localPath: resolved,
      repository: repository.fullName,
      branch: input.branch,
      remoteName: input.remoteName,
      commitMessage: input.commitMessage,
      includePaths: input.includePaths,
      allowSensitiveFiles: input.allowSensitiveFiles,
    });
    return { repository, published };
  } catch (error) {
    throw new Error(
      `Repository ${repository.fullName} was created, but publishing failed: ${userFacingError(error)}`,
    );
  }
}

async function dispatch(input: z.infer<typeof actionSchema>): Promise<unknown> {
  switch (input.action) {
    case "create":
      return createRepository(input);
    case "create_and_publish":
      return createAndPublish(input);
    case "publish":
      return publishCode(input);
    case "sync":
      return syncChanges(input);
    case "pull":
      return pullRepository(input);
    case "clone":
      return cloneRepository(input);
    case "status":
      return repositoryStatus(input.localPath);
  }
}

server.registerTool(
  "github_repository",
  {
    title: "Auto publish Codex code to GitHub",
    description:
      "Use this when the user asks Codex to create code and then automatically create a GitHub repository, commit the generated project, push it, publish code, sync changes, pull, clone, or check repository status. Select the operation with action.",
    inputSchema: actionSchema,
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false },
  },
  async input => {
    try {
      return textResult(await dispatch(input));
    } catch (error) {
      return errorResult(error);
    }
  },
);

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(error => {
  console.error(userFacingError(error));
  process.exitCode = 1;
});
