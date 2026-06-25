import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-manual-edits-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before manual edit tests.");
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
      join(projectRoot, "src", "manualEdits.ts"),
    ],
    { stdio: "inherit" },
  );

  const manualEdits = await import(pathToFileURL(join(outDir, "manualEdits.js")).href);

  const employees = [
    { id: "emp_1", name: "Kim" },
    { id: "emp_2", name: "Lee" },
  ];
  const assignment = {
    id: "assign_1",
    slot_id: "slot_1",
    role_id: "role_senior",
    employee_id: "emp_1",
    locked_by_user: false,
    source: "solver",
  };

  const draft = manualEdits.openManualEditDraft({
    slotId: "slot_1",
    roleId: "role_senior",
    employees,
    assignment,
  });
  assert.deepEqual(draft, {
    slotId: "slot_1",
    roleId: "role_senior",
    employeeId: "emp_1",
    lockedByUser: false,
  });

  assert.deepEqual(manualEdits.manualEditRequest(draft), {
    slot_id: "slot_1",
    role_id: "role_senior",
    employee_id: "emp_1",
    locked_by_user: false,
  });

  const saved = {
    ...assignment,
    id: "assign_manual",
    employee_id: "emp_2",
    employee_name: "Lee",
    source: "manual",
    locked_by_user: true,
  };
  assert.deepEqual(manualEdits.mergeSavedAssignment([assignment], saved), [saved]);
  assert.equal(manualEdits.assignmentSourceLabel(saved), "수동");
  assert.equal(manualEdits.assignmentLockLabel(saved), "잠금");
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
