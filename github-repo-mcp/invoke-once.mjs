import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const projectPath = "C:\\Users\\xyh\\Documents\\Codex\\2026-07-25\\wo\\outputs\\mcp-tools";
const serverPath = "C:\\Users\\xyh\\Documents\\Codex\\2026-07-25\\wo\\outputs\\github-repo-mcp\\dist\\src\\index.js";

const transport = new StdioClientTransport({
  command: process.execPath,
  args: [serverPath],
  env: {
    ...process.env,
    GITHUB_MCP_ALLOWED_ROOTS: "C:\\Users\\xyh\\Documents\\Codex\\2026-07-25\\wo\\outputs",
    GITHUB_MCP_GIT_NAME: "R2C-IDS Automation",
    GITHUB_MCP_GIT_EMAIL: "r2c-ids@local.invalid",
  },
});

const client = new Client({ name: "github-repo-mcp-live-invocation", version: "1.0.0" });

try {
  await client.connect(transport);
  const result = await client.callTool({
    name: "github_repository",
    arguments: {
      action: "create_and_publish",
      localPath: projectPath,
      name: "mcp-tools",
      description: "A monorepo collection of reusable MCP servers and tooling.",
      private: true,
      branch: "main",
      commitMessage: "chore: publish MCP tools monorepo",
    },
  });

  console.log(JSON.stringify(result, null, 2));
  if (result.isError) process.exitCode = 1;
} finally {
  await client.close();
}
