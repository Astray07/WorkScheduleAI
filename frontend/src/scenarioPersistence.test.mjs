import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-scenario-persistence-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

class MemoryStorage {
  values = new Map();

  getItem(key) {
    return this.values.has(key) ? this.values.get(key) : null;
  }

  setItem(key, value) {
    this.values.set(key, value);
  }
}

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before scenario persistence tests.");
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
      join(projectRoot, "src", "scenarioPersistence.ts"),
      join(projectRoot, "src", "scenario.ts"),
      join(projectRoot, "src", "scenarioTables.ts"),
      join(projectRoot, "src", "scenarioDraft.ts"),
      join(projectRoot, "src", "shiftProfile.ts"),
    ],
    { stdio: "inherit" },
  );

  const persistence = await import(pathToFileURL(join(outDir, "scenarioPersistence.js")).href);
  const scenario = await import(pathToFileURL(join(outDir, "scenario.js")).href);
  const tables = await import(pathToFileURL(join(outDir, "scenarioTables.js")).href);
  const shiftProfile = await import(pathToFileURL(join(outDir, "shiftProfile.js")).href);
  const storage = new MemoryStorage();
  const draft = {
    scenario: { ...scenario.DEFAULT_SCENARIO_CONFIG, employeeCount: 12 },
    shiftCoverage: shiftProfile.DEFAULT_SHIFT_COVERAGE,
    employeeRows: tables.buildEmployeeTableRows(12),
    vacationRows: tables.buildVacationTableRows({ ...scenario.DEFAULT_SCENARIO_CONFIG, employeeCount: 12 }),
    pairRows: tables.buildPairTableRows({ ...scenario.DEFAULT_SCENARIO_CONFIG, employeeCount: 12 }),
  };

  persistence.saveScenarioWorkspaceDraft(storage, draft);
  const restored = persistence.loadScenarioWorkspaceDraft(storage);

  assert.equal(restored.scenario.employeeCount, 12);
  assert.equal(restored.employeeRows.length, 12);
  assert.equal(restored.vacationRows.length, 3);
  assert.equal(restored.pairRows.length, 3);
  assert.deepEqual(restored.shiftCoverage, shiftProfile.DEFAULT_SHIFT_COVERAGE);

  storage.setItem(persistence.SCENARIO_WORKSPACE_DRAFT_KEY, "not json");
  const fallback = persistence.loadScenarioWorkspaceDraft(storage);
  assert.equal(fallback.scenario.employeeCount, scenario.DEFAULT_SCENARIO_CONFIG.employeeCount);
  assert.equal(fallback.employeeRows.length, scenario.DEFAULT_SCENARIO_CONFIG.employeeCount);
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
