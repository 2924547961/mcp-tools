import assert from "node:assert/strict";
import test from "node:test";
import { cloneUrlFor, parseRepositoryReference } from "../src/github.js";

test("parseRepositoryReference accepts owner/name", () => {
  assert.deepEqual(parseRepositoryReference("openai/example"), {
    owner: "openai",
    name: "example",
  });
});

test("parseRepositoryReference accepts HTTPS and SSH URLs", () => {
  assert.deepEqual(parseRepositoryReference("https://github.com/openai/example.git"), {
    owner: "openai",
    name: "example",
  });
  assert.deepEqual(parseRepositoryReference("git@github.com:openai/example.git"), {
    owner: "openai",
    name: "example",
  });
});

test("cloneUrlFor normalizes references", () => {
  assert.equal(cloneUrlFor("openai/example"), "https://github.com/openai/example.git");
});

test("invalid repository references are rejected", () => {
  assert.throws(() => parseRepositoryReference("example"), /Invalid GitHub repository reference/);
});
