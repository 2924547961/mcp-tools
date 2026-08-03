import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

test("stdio MCP server starts and exposes the expected tools", async () => {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  const serverPath = path.resolve(currentDir, "../src/index.js");
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [serverPath],
    env: {
      ...process.env,
      GITHUB_MCP_ALLOWED_ROOTS: process.cwd(),
    },
  });
  const client = new Client({ name: "github-repo-mcp-test", version: "0.1.0" });

  try {
    await client.connect(transport);
    const response = await client.listTools();
    const names = response.tools.map(tool => tool.name).sort();
    assert.deepEqual(names, ["github_repository"]);

    const status = await client.callTool({
      name: "github_repository",
      arguments: { action: "status", localPath: process.cwd() },
    });
    assert.equal(status.isError, undefined);
    assert.ok(Array.isArray(status.content));
    const content = status.content as Array<{ type?: string }>;
    assert.equal(content[0]?.type, "text");
  } finally {
    await client.close();
  }
});
