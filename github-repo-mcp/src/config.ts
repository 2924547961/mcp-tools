import fs from "node:fs";
import path from "node:path";

function canonicalize(targetPath: string): string {
  const absolute = path.resolve(targetPath);
  let existing = absolute;

  while (!fs.existsSync(existing)) {
    const parent = path.dirname(existing);
    if (parent === existing) {
      break;
    }
    existing = parent;
  }

  if (!fs.existsSync(existing)) {
    return absolute;
  }

  const realExisting = fs.realpathSync.native(existing);
  return path.resolve(realExisting, path.relative(existing, absolute));
}

function comparable(value: string): string {
  const normalized = path.normalize(value);
  const withoutTrailingSeparators = normalized === path.parse(normalized).root
    ? normalized
    : normalized.replace(/[\\/]+$/, "");
  return process.platform === "win32"
    ? withoutTrailingSeparators.toLowerCase()
    : withoutTrailingSeparators;
}

export function parseAllowedRoots(raw = process.env.GITHUB_MCP_ALLOWED_ROOTS): string[] {
  const values = raw
    ? raw.split(path.delimiter).map(value => value.trim()).filter(Boolean)
    : [process.cwd()];
  return values.map(canonicalize);
}

export function isPathInside(candidate: string, root: string): boolean {
  const relative = path.relative(comparable(root), comparable(candidate));
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

export function assertAllowedPath(
  requestedPath: string,
  options: { mustExist?: boolean; allowedRoots?: string[] } = {},
): string {
  const mustExist = options.mustExist ?? true;
  const candidate = canonicalize(requestedPath);
  const roots = options.allowedRoots ?? parseAllowedRoots();

  if (mustExist && !fs.existsSync(candidate)) {
    throw new Error(`Local path does not exist: ${candidate}`);
  }
  if (!roots.some(root => isPathInside(candidate, root))) {
    throw new Error(
      `Local path is outside GITHUB_MCP_ALLOWED_ROOTS: ${candidate}. Allowed roots: ${roots.join(", ")}`,
    );
  }
  return candidate;
}

export function gitExecutable(): string {
  return process.env.GITHUB_MCP_GIT_PATH?.trim() || "git";
}
