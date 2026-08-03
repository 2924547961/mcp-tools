import { spawn } from "node:child_process";

export interface CommandResult {
  command: string;
  args: string[];
  code: number;
  stdout: string;
  stderr: string;
}

export interface CommandOptions {
  cwd?: string;
  input?: string;
  env?: NodeJS.ProcessEnv;
  timeoutMs?: number;
  allowExitCodes?: number[];
}

export class CommandError extends Error {
  constructor(public readonly result: CommandResult) {
    const details = result.stderr.trim() || result.stdout.trim() || `exit code ${result.code}`;
    super(`${result.command} failed: ${details}`);
    this.name = "CommandError";
  }
}

export function runCommand(
  command: string,
  args: string[],
  options: CommandOptions = {},
): Promise<CommandResult> {
  const timeoutMs = options.timeoutMs ?? 120_000;
  const allowed = options.allowExitCodes ?? [0];

  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env ?? process.env,
      shell: false,
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => (stdout += chunk));
    child.stderr.on("data", (chunk: string) => (stderr += chunk));

    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`${command} timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    child.on("error", error => {
      clearTimeout(timer);
      reject(error);
    });

    child.on("close", code => {
      clearTimeout(timer);
      const result: CommandResult = {
        command,
        args,
        code: code ?? -1,
        stdout,
        stderr,
      };
      if (allowed.includes(result.code)) {
        resolve(result);
      } else {
        reject(new CommandError(result));
      }
    });

    if (options.input !== undefined) {
      child.stdin.write(options.input);
    }
    child.stdin.end();
  });
}
