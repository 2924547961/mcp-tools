import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { SyncError } from "../src/auto-sync-types.js";
import { scanSensitiveFiles } from "../src/safe-sync.js";

function withFile(name: string, content: string, run: (root: string) => void): void {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "github-auto-sync-secret-"));
  try {
    fs.writeFileSync(path.join(root, name), content);
    run(root);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

test("credential scanner rejects a real-looking JSON password", () => {
  withFile("config.json", "{\n  \"password\": \"realSecretValue123456\"\n}\n", root => {
    assert.throws(
      () => scanSensitiveFiles(root, ["config.json"]),
      error => error instanceof SyncError && error.code === "sensitive_content",
    );
  });
});

test("credential scanner accepts explicit placeholders", () => {
  withFile("config.example.json", "{\n  \"password\": \"placeholder\"\n}\n", root => {
    assert.doesNotThrow(() => scanSensitiveFiles(root, ["config.example.json"]));
  });
});

test("credential scanner does not treat source variable assignment as a secret", () => {
  withFile("source.ts", "const password = credential.stdout;\n", root => {
    assert.doesNotThrow(() => scanSensitiveFiles(root, ["source.ts"]));
  });
});
