import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-run-comparison-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before run comparison tests.");
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
      join(projectRoot, "src", "runComparison.ts"),
    ],
    { stdio: "inherit" },
  );

  const runComparison = await import(pathToFileURL(join(outDir, "runComparison.js")).href);

  const comparison = {
    summary: {
      assignment_added_count: 2,
      assignment_removed_count: 1,
      assignment_unchanged_count: 3,
      manual_lock_maintained_count: 1,
      issue_added_count: 1,
      issue_resolved_count: 2,
      fairness_changed_employee_count: 2,
    },
    assignment_changes: [
      { change_type: "unchanged", manual_lock_maintained: true },
      { change_type: "added", manual_lock_maintained: false },
      { change_type: "removed", manual_lock_maintained: false },
    ],
    issue_changes: [
      { change_type: "resolved", missing_delta: -1 },
      { change_type: "added", missing_delta: 2 },
    ],
    fairness_changes: [
      { employee_id: "emp_1", employee_name: "Kim", assignment_delta: -1 },
      { employee_id: "emp_2", employee_name: "Lee", assignment_delta: 2 },
      { employee_id: "emp_3", employee_name: "Park", assignment_delta: 0 },
    ],
  };

  assert.deepEqual(runComparison.comparisonSummaryMetrics(comparison), [
    { label: "추가 배정", value: "2건" },
    { label: "삭제 배정", value: "1건" },
    { label: "수동 잠금 유지", value: "1건" },
    { label: "이슈 변화", value: "+1 / -2" },
  ]);
  assert.deepEqual(
    runComparison.changedFairnessRows(comparison).map((row) => row.employee_id),
    ["emp_2", "emp_1"],
  );
  assert.equal(runComparison.changeTypeLabel("unchanged"), "유지");
  assert.equal(runComparison.changeTypeLabel("added"), "추가");
  assert.equal(runComparison.changeTypeLabel("removed"), "삭제");
  assert.equal(runComparison.deltaLabel(2), "+2");
  assert.equal(runComparison.deltaLabel(-1), "-1");
  assert.equal(runComparison.deltaLabel(0), "0");
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
