import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-scenario-draft-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before scenario draft tests.");
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
      join(projectRoot, "src", "scenarioDraft.ts"),
    ],
    { stdio: "inherit" },
  );

  const draft = await import(pathToFileURL(join(outDir, "scenarioDraft.js")).href);

  const employees = draft.parseEmployeeDraft(`
E001,Kim,사수
E002,Lee,부사수,4
E003,Park,사수|부사수
`);
  assert.deepEqual(employees, [
    { rowNo: 1, employeeCode: "E001", name: "Kim", roleNames: ["사수"], maxShiftsPerWeek: 5 },
    { rowNo: 2, employeeCode: "E002", name: "Lee", roleNames: ["부사수"], maxShiftsPerWeek: 4 },
    {
      rowNo: 3,
      employeeCode: "E003",
      name: "Park",
      roleNames: ["사수", "부사수"],
      maxShiftsPerWeek: 5,
    },
  ]);

  const vacations = draft.parseVacationDraft(`
E002,2026-08-03
E004,2026-08-05,personal,false
`);
  assert.deepEqual(vacations, [
    { employeeCode: "E002", date: "2026-08-03", type: "vacation", overrideAllowed: true },
    { employeeCode: "E004", date: "2026-08-05", type: "personal", overrideAllowed: false },
  ]);

  const pairs = draft.parsePairDraft(`
E001,E002
E003,E004,medium,false
`);
  assert.deepEqual(pairs, [
    { employeeACode: "E001", employeeBCode: "E002", severity: "high", overrideAllowed: true },
    { employeeACode: "E003", employeeBCode: "E004", severity: "medium", overrideAllowed: false },
  ]);

  assert.equal(
    draft.formatEmployeeDraft(employees),
    "E001,Kim,사수,5\nE002,Lee,부사수,4\nE003,Park,사수|부사수,5",
  );
  assert.equal(
    draft.buildDraftSummary({ employeeDraft: draft.formatEmployeeDraft(employees), vacationDraft: "E002,2026-08-03", pairDraft: "E001,E002", periodDays: 14 }),
    "직원 3명, 휴가 1건, 상극 1건, 14일 생성",
  );

  assert.throws(
    () => draft.parseEmployeeDraft("E001,Kim,사수\nE001,Lee,부사수"),
    /Duplicate employee_code E001/,
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
