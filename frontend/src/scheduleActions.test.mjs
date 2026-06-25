import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-schedule-actions-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before schedule action tests.");
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
      join(projectRoot, "src", "scheduleActions.ts"),
    ],
    { stdio: "inherit" },
  );

  const actions = await import(pathToFileURL(join(outDir, "scheduleActions.js")).href);

  assert.equal(actions.canRecalculate(null), false);
  assert.equal(actions.canRecalculate({ proposals: [] }), false);
  assert.equal(
    actions.canRecalculate({ proposals: [{ id: "proposal_1", status: "recommended" }] }),
    false,
  );
  assert.equal(
    actions.canRecalculate({ proposals: [{ id: "proposal_1", status: "approved" }] }),
    true,
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
