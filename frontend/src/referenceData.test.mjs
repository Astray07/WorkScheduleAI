import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-reference-data-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before reference data tests.");
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
      join(projectRoot, "src", "referenceData.ts"),
    ],
    { stdio: "inherit" },
  );

  const referenceData = await import(pathToFileURL(join(outDir, "referenceData.js")).href);

  assert.deepEqual(
    referenceData.REFERENCE_TABS.map((tab) => tab.id),
    ["scenario", "reference", "policy", "import"],
  );
  assert.equal(
    referenceData.referenceSummary({
      employees: [{ id: "emp_1" }, { id: "emp_2" }],
      unavailabilities: [{ id: "unav_1" }],
      pairConstraints: [{ id: "pair_1" }],
      shiftTypes: [{ id: "shift_type_1" }, { id: "shift_type_2" }],
    }),
    "직원 2명 · 일정 1건 · 조합 1건 · 근무유형 2개",
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
