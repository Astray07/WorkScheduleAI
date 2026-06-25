import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-scenario-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before scenario tests.");
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
      join(projectRoot, "src", "scenario.ts"),
    ],
    { stdio: "inherit" },
  );

  const scenario = await import(pathToFileURL(join(outDir, "scenario.js")).href);
  const employees = scenario.buildScenarioEmployees(12);

  assert.equal(scenario.DEFAULT_SCENARIO_CONFIG.periodDays, 31);
  assert.equal(scenario.DEFAULT_SCENARIO_CONFIG.organizationName, "하나케어 운영팀");
  assert.equal(employees.length, 12);
  assert.equal(employees[0].employeeCode, "E001");
  assert.equal(employees[0].name, "김민준");
  assert.equal(employees[1].name, "이서연");
  assert.equal(employees[11].employeeCode, "E012");
  assert.deepEqual(employees[0].roleNames, ["사수"]);
  assert.deepEqual(employees[1].roleNames, ["부사수"]);
  assert.deepEqual(employees[2].roleNames, ["사수", "부사수"]);
  assert.ok(employees.filter((employee) => employee.roleNames.includes("사수")).length >= 6);
  assert.ok(employees.filter((employee) => employee.roleNames.includes("부사수")).length >= 6);

  assert.equal(scenario.addDaysIso("2026-07-01", 30), "2026-07-31");
  assert.equal(scenario.periodEndFor("2026-07-01", 31), "2026-07-31");
  assert.equal(scenario.periodDaysForRange("2026-07-01", "2026-07-10"), 10);
  assert.equal(scenario.periodDaysForRange("2026-07-01", "2026-08-15"), 31);
  assert.equal(scenario.periodDaysForRange("2026-07-10", "2026-07-01"), 1);

  const defaultVacations = scenario.buildDefaultVacationDrafts(scenario.DEFAULT_SCENARIO_CONFIG);
  assert.deepEqual(defaultVacations, [
    {
      employeeCode: "E002",
      startDate: "2026-07-02",
      endDate: "2026-07-04",
      type: "vacation",
      overrideAllowed: true,
    },
    {
      employeeCode: "E007",
      startDate: "2026-07-15",
      endDate: "2026-07-17",
      type: "vacation",
      overrideAllowed: true,
    },
    {
      employeeCode: "E010",
      startDate: "2026-07-20",
      endDate: "2026-07-20",
      type: "personal",
      overrideAllowed: true,
    },
  ]);

  const defaultPairs = scenario.buildDefaultPairDrafts(scenario.DEFAULT_SCENARIO_CONFIG);
  assert.deepEqual(defaultPairs, [
    {
      employeeACode: "E001",
      employeeBCode: "E002",
      severity: "high",
      overrideAllowed: true,
    },
    {
      employeeACode: "E003",
      employeeBCode: "E004",
      severity: "medium",
      overrideAllowed: true,
    },
    {
      employeeACode: "E005",
      employeeBCode: "E006",
      severity: "medium",
      overrideAllowed: true,
    },
  ]);
  assert.deepEqual(
    scenario.buildDefaultPairDrafts({ ...scenario.DEFAULT_SCENARIO_CONFIG, employeeCount: 4 }),
    [
      {
        employeeACode: "E001",
        employeeBCode: "E002",
        severity: "high",
        overrideAllowed: true,
      },
      {
        employeeACode: "E003",
        employeeBCode: "E004",
        severity: "medium",
        overrideAllowed: true,
      },
    ],
  );

  const normalized = scenario.normalizeScenarioConfig({
    employeeCount: 100,
    organizationName: "",
    periodDays: 99,
    startDate: "2026-07-01",
    vacationEmployeeCode: "E999",
    vacationDate: "2026-07-02",
    vacationEndDate: "2026-07-04",
    pairEmployeeACode: "E005",
    pairEmployeeBCode: "E005",
  });

  assert.equal(normalized.organizationName, "하나케어 운영팀");
  assert.equal(normalized.employeeCount, 50);
  assert.equal(normalized.periodDays, 31);
  assert.equal(normalized.vacationEmployeeCode, "E002");
  assert.equal(normalized.pairEmployeeACode, "E005");
  assert.equal(normalized.pairEmployeeBCode, "E006");

  assert.equal(
    scenario.normalizeScenarioConfig({
      ...scenario.DEFAULT_SCENARIO_CONFIG,
      periodDays: 10,
    }).periodDays,
    10,
  );

  assert.equal(
    scenario.buildScenarioSummary(normalized),
    "직원 50명, 휴가 E002, 상극 E005/E006, 31일 생성",
  );

  assert.equal(scenario.dateDisplayLabel("2026-07-01"), "2026-07-01 (수)");
  assert.equal(scenario.dateDisplayLabel("2026-07-04"), "2026-07-04 (토)");
  assert.equal(scenario.dayTypeLabel("2026-07-03"), "평일");
  assert.equal(scenario.dayTypeLabel("2026-07-04"), "주말");
  assert.equal(scenario.slotDisplayLabel("주간 근무", "2026-07-04"), "주간 근무 · 주말");
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
