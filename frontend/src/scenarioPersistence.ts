import {
  DEFAULT_SCENARIO_CONFIG,
  normalizeScenarioConfig,
  type ScenarioConfig,
} from "./scenario.js";
import {
  buildEmployeeTableRows,
  buildPairTableRows,
  buildVacationTableRows,
  normalizePairRowsForEmployees,
  normalizeVacationRowsForEmployees,
  type EmployeeTableRow,
  type PairTableRow,
  type VacationTableRow,
} from "./scenarioTables.js";
import {
  DEFAULT_SHIFT_COVERAGE,
  normalizeShiftCoverage,
  type ShiftCoverage,
} from "./shiftProfile.js";

export const SCENARIO_WORKSPACE_DRAFT_KEY = "workscheduleai.scenarioWorkspaceDraft.v1";

export type ScenarioWorkspaceDraft = {
  scenario: ScenarioConfig;
  shiftCoverage: ShiftCoverage;
  employeeRows: EmployeeTableRow[];
  vacationRows: VacationTableRow[];
  pairRows: PairTableRow[];
};

type DraftStorage = {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
};

export function defaultScenarioWorkspaceDraft(): ScenarioWorkspaceDraft {
  const scenario = normalizeScenarioConfig(DEFAULT_SCENARIO_CONFIG);
  const employeeRows = buildEmployeeTableRows(scenario.employeeCount);
  return {
    scenario,
    shiftCoverage: normalizeShiftCoverage(DEFAULT_SHIFT_COVERAGE),
    employeeRows,
    vacationRows: buildVacationTableRows(scenario),
    pairRows: buildPairTableRows(scenario),
  };
}

export function loadScenarioWorkspaceDraft(
  storage: DraftStorage | null | undefined,
): ScenarioWorkspaceDraft {
  if (!storage) return defaultScenarioWorkspaceDraft();
  try {
    const stored = storage.getItem(SCENARIO_WORKSPACE_DRAFT_KEY);
    if (!stored) return defaultScenarioWorkspaceDraft();
    return normalizeScenarioWorkspaceDraft(JSON.parse(stored));
  } catch {
    return defaultScenarioWorkspaceDraft();
  }
}

export function saveScenarioWorkspaceDraft(
  storage: DraftStorage | null | undefined,
  draft: ScenarioWorkspaceDraft,
): void {
  if (!storage) return;
  try {
    storage.setItem(
      SCENARIO_WORKSPACE_DRAFT_KEY,
      JSON.stringify(normalizeScenarioWorkspaceDraft(draft)),
    );
  } catch {
    // Storage can be disabled or full. The app should keep working without persistence.
  }
}

export function normalizeScenarioWorkspaceDraft(value: unknown): ScenarioWorkspaceDraft {
  if (!isRecord(value)) return defaultScenarioWorkspaceDraft();
  const scenario = normalizeScenarioConfig({
    ...DEFAULT_SCENARIO_CONFIG,
    ...(isRecord(value.scenario) ? value.scenario : {}),
  } as ScenarioConfig);
  const employeeRows = normalizeEmployeeRows(value.employeeRows, scenario.employeeCount);
  const normalizedScenario = normalizeScenarioConfig({
    ...scenario,
    employeeCount: employeeRows.length,
  });
  const vacationRows = normalizeVacationRowsForEmployees(
    normalizeVacationRows(value.vacationRows, normalizedScenario),
    employeeRows,
  );
  const pairRows = normalizePairRowsForEmployees(
    normalizePairRows(value.pairRows, normalizedScenario),
    employeeRows,
  );
  return {
    scenario: normalizedScenario,
    shiftCoverage: normalizeShiftCoverage(
      isShiftCoverage(value.shiftCoverage) ? value.shiftCoverage : DEFAULT_SHIFT_COVERAGE,
    ),
    employeeRows,
    vacationRows,
    pairRows,
  };
}

function normalizeEmployeeRows(value: unknown, fallbackCount: number): EmployeeTableRow[] {
  if (!Array.isArray(value)) return buildEmployeeTableRows(fallbackCount);
  const rows = value.flatMap((row): EmployeeTableRow[] => {
    if (!isRecord(row)) return [];
    const employeeCode = stringValue(row.employeeCode);
    const name = stringValue(row.name);
    const roleNames = Array.isArray(row.roleNames)
      ? row.roleNames.filter((roleName): roleName is string => typeof roleName === "string")
      : [];
    const maxShiftsPerWeek = Number(row.maxShiftsPerWeek);
    if (!employeeCode || !name || !roleNames.length || !Number.isFinite(maxShiftsPerWeek)) {
      return [];
    }
    return [
      {
        id: stringValue(row.id) || `employee-${employeeCode}`,
        employeeCode,
        name,
        roleNames,
        maxShiftsPerWeek,
      },
    ];
  });
  return rows.length ? rows : buildEmployeeTableRows(fallbackCount);
}

function normalizeVacationRows(value: unknown, scenario: ScenarioConfig): VacationTableRow[] {
  if (!Array.isArray(value)) return buildVacationTableRows(scenario);
  const rows = value.flatMap((row): VacationTableRow[] => {
    if (!isRecord(row)) return [];
    const employeeCode = stringValue(row.employeeCode);
    const startDate = stringValue(row.startDate);
    const endDate = stringValue(row.endDate);
    if (!employeeCode || !startDate || !endDate) return [];
    return [
      {
        id: stringValue(row.id) || `vacation-${employeeCode}-${startDate}`,
        employeeCode,
        startDate,
        endDate,
        type: stringValue(row.type) || "vacation",
        overrideAllowed: typeof row.overrideAllowed === "boolean" ? row.overrideAllowed : true,
      },
    ];
  });
  return rows.length ? rows : buildVacationTableRows(scenario);
}

function normalizePairRows(value: unknown, scenario: ScenarioConfig): PairTableRow[] {
  if (!Array.isArray(value)) return buildPairTableRows(scenario);
  const rows = value.flatMap((row): PairTableRow[] => {
    if (!isRecord(row)) return [];
    const employeeACode = stringValue(row.employeeACode);
    const employeeBCode = stringValue(row.employeeBCode);
    if (!employeeACode || !employeeBCode) return [];
    return [
      {
        id: stringValue(row.id) || `pair-${employeeACode}-${employeeBCode}`,
        employeeACode,
        employeeBCode,
        severity: stringValue(row.severity) || "high",
        overrideAllowed: typeof row.overrideAllowed === "boolean" ? row.overrideAllowed : true,
      },
    ];
  });
  return rows.length ? rows : buildPairTableRows(scenario);
}

function isShiftCoverage(value: unknown): value is ShiftCoverage {
  return isRecord(value) && Array.isArray(value.weekday) && Array.isArray(value.weekend);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
