import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-visibility-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before visibility tests.");
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
      join(projectRoot, "src", "visibility.ts"),
    ],
    { stdio: "inherit" },
  );

  const visibility = await import(pathToFileURL(join(outDir, "visibility.js")).href);

  assert.equal(visibility.auditActionLabel("manual_assignment_saved"), "수동 배정 저장");
  assert.equal(visibility.auditActionLabel("publication_created"), "근무표 확정");
  assert.equal(visibility.auditActionLabel("unknown_action"), "unknown_action");

  assert.equal(visibility.fairnessSpreadLabel({ spread: 0 }), "균등");
  assert.equal(visibility.fairnessSpreadLabel({ spread: 2 }), "편차 2회");
  assert.equal(visibility.fairnessDeltaLabel(1.334), "+1.33");
  assert.equal(visibility.fairnessDeltaLabel(-0.667), "-0.67");
  assert.equal(visibility.longTermFairnessSourceLabel("publications"), "확정본");
  assert.equal(visibility.longTermFairnessSourceLabel("runs"), "실행 기록");
  assert.deepEqual(
    visibility.sortedLongTermFairnessRows([
      {
        employee_code: "E002",
        employee_name: "이서연",
        assignment_count: 3,
        night_count: 0,
        weekend_count: 0,
        delta_from_average: 0.5,
      },
      {
        employee_code: "E001",
        employee_name: "김민준",
        assignment_count: 6,
        night_count: 2,
        weekend_count: 1,
        delta_from_average: 3.5,
      },
      {
        employee_code: "E003",
        employee_name: "박지훈",
        assignment_count: 0,
        night_count: 0,
        weekend_count: 0,
        delta_from_average: -2.5,
      },
    ]).map((row) => row.employee_code),
    ["E001", "E003", "E002"],
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
