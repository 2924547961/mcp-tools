import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { assertAllowedPath, isPathInside } from "../src/config.js";

test("isPathInside accepts a root and its descendants", () => {
  const root = path.resolve("workspace");
  assert.equal(isPathInside(root, root), true);
  assert.equal(isPathInside(path.join(root, "project"), root), true);
  assert.equal(isPathInside(path.resolve("outside"), root), false);
});

test("isPathInside accepts descendants of a filesystem root", () => {
  const filesystemRoot = path.parse(process.cwd()).root;
  assert.equal(isPathInside(process.cwd(), filesystemRoot), true);
});

test("assertAllowedPath rejects paths outside configured roots", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "github-repo-mcp-root-"));
  const inside = path.join(root, "project");
  fs.mkdirSync(inside);
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), "github-repo-mcp-outside-"));

  try {
    assert.equal(assertAllowedPath(inside, { allowedRoots: [root] }), fs.realpathSync.native(inside));
    assert.throws(
      () => assertAllowedPath(outside, { allowedRoots: [root] }),
      /outside GITHUB_MCP_ALLOWED_ROOTS/,
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
    fs.rmSync(outside, { recursive: true, force: true });
  }
});

test("assertAllowedPath validates a not-yet-created clone target through its parent", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "github-repo-mcp-clone-"));
  try {
    const target = path.join(root, "new-repository");
    assert.equal(
      assertAllowedPath(target, { mustExist: false, allowedRoots: [root] }),
      path.resolve(target),
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
