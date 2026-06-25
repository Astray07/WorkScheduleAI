import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-scenario-tables-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before scenario table tests.");
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
      join(projectRoot, "src", "scenarioTables.ts"),
    ],
    { stdio: "inherit" },
  );

  const scenario = await import(pathToFileURL(join(outDir, "scenario.js")).href);
  const tables = await import(pathToFileURL(join(outDir, "scenarioTables.js")).href);

  const employees = tables.buildEmployeeTableRows(4);
  assert.equal(employees.length, 4);
  assert.deepEqual(employees[0], {
    id: "employee-E001",
    employeeCode: "E001",
    name: "김민준",
    roleNames: ["사수"],
    maxShiftsPerWeek: 5,
  });

  const protectedRole = tables.setEmployeeRole(employees, "employee-E001", "사수", false);
  assert.deepEqual(protectedRole[0].roleNames, ["사수"]);

  const expandedRole = tables.setEmployeeRole(employees, "employee-E001", "부사수", true);
  assert.deepEqual(expandedRole[0].roleNames, ["사수", "부사수"]);

  assert.equal(tables.removeEmployeeRow(employees, "employee-E004").length, 4);
  assert.deepEqual(
    tables.removeEmployeeRow(tables.buildEmployeeTableRows(5), "employee-E005").map((row) => row.employeeCode),
    ["E001", "E002", "E003", "E004"],
  );
  assert.equal(tables.appendEmployeeRow(employees).at(-1).employeeCode, "E005");

  assert.deepEqual(tables.employeeRowsToBulkRows(employees), [
    {
      row_no: 1,
      employee_code: "E001",
      name: "김민준",
      role_names: ["사수"],
      max_shifts_per_week: 5,
    },
    {
      row_no: 2,
      employee_code: "E002",
      name: "이서연",
      role_names: ["부사수"],
      max_shifts_per_week: 5,
    },
    {
      row_no: 3,
      employee_code: "E003",
      name: "박지훈",
      role_names: ["사수", "부사수"],
      max_shifts_per_week: 5,
    },
    {
      row_no: 4,
      employee_code: "E004",
      name: "최하은",
      role_names: ["사수", "부사수"],
      max_shifts_per_week: 5,
    },
  ]);

  const vacations = tables.buildVacationTableRows(scenario.DEFAULT_SCENARIO_CONFIG);
  assert.equal(vacations.length, 3);
  assert.deepEqual(vacations[0], {
    id: "vacation-1",
    employeeCode: "E002",
    startDate: "2026-07-02",
    endDate: "2026-07-04",
    type: "vacation",
    overrideAllowed: true,
  });
  assert.equal(tables.removeVacationRow([vacations[0]], "vacation-1").length, 1);

  const normalizedVacation = tables.updateVacationRow(vacations, "vacation-1", {
    startDate: "2026-07-10",
    endDate: "2026-07-08",
  });
  assert.equal(normalizedVacation[0].endDate, "2026-07-10");

  assert.deepEqual(tables.vacationRowsToDrafts([normalizedVacation[0]]), [
    {
      employeeCode: "E002",
      startDate: "2026-07-10",
      endDate: "2026-07-10",
      type: "vacation",
      overrideAllowed: true,
    },
  ]);

  const reducedEmployees = tables.buildEmployeeTableRows(4);
  assert.equal(
    tables.normalizeVacationRowsForEmployees(
      [{ ...vacations[1], employeeCode: "E007" }],
      reducedEmployees,
    )[0].employeeCode,
    "E001",
  );

  const appendedVacation = tables.appendVacationRow([], employees, "2026-07-01");
  assert.deepEqual(appendedVacation, [
    {
      id: "vacation-1",
      employeeCode: "E001",
      startDate: "2026-07-01",
      endDate: "2026-07-01",
      type: "vacation",
      overrideAllowed: true,
    },
  ]);

  const pairs = tables.buildPairTableRows(scenario.DEFAULT_SCENARIO_CONFIG);
  assert.equal(pairs.length, 3);
  assert.deepEqual(pairs[0], {
    id: "pair-1",
    employeeACode: "E001",
    employeeBCode: "E002",
    severity: "high",
    overrideAllowed: true,
  });
  assert.equal(tables.removePairRow([pairs[0]], "pair-1").length, 1);

  const normalizedPair = tables.updatePairRow(pairs, "pair-1", { employeeBCode: "E001" }, employees);
  assert.equal(normalizedPair[0].employeeACode, "E001");
  assert.equal(normalizedPair[0].employeeBCode, "E002");

  assert.deepEqual(
    tables.normalizePairRowsForEmployees(
      [{ ...pairs[2], employeeACode: "E005", employeeBCode: "E006" }],
      reducedEmployees,
    )[0],
    {
      id: "pair-3",
      employeeACode: "E001",
      employeeBCode: "E002",
      severity: "medium",
      overrideAllowed: true,
    },
  );

  assert.deepEqual(tables.pairRowsToDrafts([normalizedPair[0]]), [
    {
      employeeACode: "E001",
      employeeBCode: "E002",
      severity: "high",
      overrideAllowed: true,
    },
  ]);

  assert.deepEqual(tables.appendPairRow([], employees), [
    {
      id: "pair-1",
      employeeACode: "E001",
      employeeBCode: "E002",
      severity: "high",
      overrideAllowed: true,
    },
  ]);
  assert.deepEqual(tables.appendPairRow(pairs, tables.buildEmployeeTableRows(12)).at(-1), {
    id: "pair-4",
    employeeACode: "E007",
    employeeBCode: "E008",
    severity: "high",
    overrideAllowed: true,
  });
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
