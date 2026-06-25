import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-policies-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before policy tests.");
}

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

try {
  execFileSync(
    process.execPath,
    [
      tscBin,
      "--target",
      "ES2022",
      "--module",
      "NodeNext",
      "--moduleResolution",
      "NodeNext",
      "--rootDir",
      join(projectRoot, "src"),
      "--outDir",
      outDir,
      join(projectRoot, "src", "policies.ts"),
    ],
    { stdio: "inherit" },
  );

  const policies = await import(pathToFileURL(join(outDir, "policies.js")).href);

  assert.equal(policies.DEFAULT_POLICY.name, "기본 정책");
  assert.equal(policies.normalizePolicy({ min_rest_hours: -1 }).min_rest_hours, 0);
  assert.equal(policies.normalizePolicy({ max_consecutive_shifts: 0 }).max_consecutive_shifts, 1);
  assert.equal(policies.unfilledPolicyLabel("soft_penalty"), "미배정 soft penalty");
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
