import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-workspace-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before workspace tests.");
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
      "ES2022",
      "--moduleResolution",
      "Node",
      "--rootDir",
      join(projectRoot, "src"),
      "--outDir",
      outDir,
      join(projectRoot, "src", "workspace.ts"),
    ],
    { stdio: "inherit" },
  );

  const { workspaceFromSession } = await import(pathToFileURL(join(outDir, "workspace.js")).href);

  assert.deepEqual(
    workspaceFromSession(
      { organization_id: "org_demo_p0" },
      [
        { id: "role_demo_senior", name: "사수" },
        { id: "role_demo_junior", name: "부사수" },
      ],
    ),
    {
      id: "org_demo_p0",
      default_roles: [
        { id: "role_demo_senior", name: "사수" },
        { id: "role_demo_junior", name: "부사수" },
      ],
    },
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
