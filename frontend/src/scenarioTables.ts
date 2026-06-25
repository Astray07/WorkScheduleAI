import {
  MAX_EMPLOYEE_COUNT,
  MIN_EMPLOYEE_COUNT,
  buildDefaultPairDrafts,
  buildDefaultVacationDrafts,
  buildScenarioEmployees,
  type ScenarioConfig,
} from "./scenario.js";
import type { PairDraft, ScenarioDraftEmployee, VacationDraft } from "./scenarioDraft.js";

export const ROLE_OPTIONS = ["사수", "부사수"] as const;
export const VACATION_TYPE_OPTIONS = ["vacation", "business_trip", "training", "personal"] as const;
export const PAIR_SEVERITY_OPTIONS = ["high", "medium", "low"] as const;

export type EmployeeTableRow = Omit<ScenarioDraftEmployee, "rowNo"> & {
  id: string;
};

export type VacationTableRow = VacationDraft & {
  id: string;
};

export type PairTableRow = PairDraft & {
  id: string;
};

export type EmployeeBulkRow = {
  row_no: number;
  employee_code: string;
  name: string;
  role_names: string[];
  max_shifts_per_week: number;
};

export function buildEmployeeTableRows(count: number): EmployeeTableRow[] {
  return buildScenarioEmployees(count).map(employeeToTableRow);
}

export function appendEmployeeRow(rows: EmployeeTableRow[]): EmployeeTableRow[] {
  if (rows.length >= MAX_EMPLOYEE_COUNT) return rows;
  const usedCodes = new Set(rows.map((row) => row.employeeCode));
  const nextNumber = Array.from({ length: MAX_EMPLOYEE_COUNT }, (_, index) => index + 1).find(
    (employeeNumber) => !usedCodes.has(employeeCodeFor(employeeNumber)),
  );
  if (!nextNumber) return rows;
  return [...rows, employeeToTableRow(buildScenarioEmployees(nextNumber)[nextNumber - 1])];
}

export function removeEmployeeRow(rows: EmployeeTableRow[], rowId: string): EmployeeTableRow[] {
  if (rows.length <= MIN_EMPLOYEE_COUNT) return rows;
  return rows.filter((row) => row.id !== rowId);
}

export function updateEmployeeRow(
  rows: EmployeeTableRow[],
  rowId: string,
  patch: Partial<Omit<EmployeeTableRow, "id">>,
): EmployeeTableRow[] {
  return rows.map((row) =>
    row.id === rowId
      ? {
          ...row,
          ...patch,
          roleNames: normalizeRoleNames(patch.roleNames ?? row.roleNames),
          maxShiftsPerWeek: normalizePositiveInteger(
            patch.maxShiftsPerWeek ?? row.maxShiftsPerWeek,
            row.maxShiftsPerWeek,
          ),
        }
      : row,
  );
}

export function setEmployeeRole(
  rows: EmployeeTableRow[],
  rowId: string,
  roleName: string,
  enabled: boolean,
): EmployeeTableRow[] {
  return rows.map((row) => {
    if (row.id !== rowId) return row;
    const currentRoles = new Set(normalizeRoleNames(row.roleNames));
    if (enabled) {
      currentRoles.add(roleName);
    } else if (currentRoles.size > 1) {
      currentRoles.delete(roleName);
    }
    return {
      ...row,
      roleNames: normalizeRoleNames(Array.from(currentRoles)),
    };
  });
}

export function employeeRowsToBulkRows(rows: EmployeeTableRow[]): EmployeeBulkRow[] {
  return rows.map((row, index) => ({
    row_no: index + 1,
    employee_code: row.employeeCode,
    name: row.name,
    role_names: normalizeRoleNames(row.roleNames),
    max_shifts_per_week: normalizePositiveInteger(row.maxShiftsPerWeek, 5),
  }));
}

export function buildVacationTableRows(config: ScenarioConfig): VacationTableRow[] {
  return buildDefaultVacationDrafts(config).map((vacation, index) => ({
    id: `vacation-${index + 1}`,
    ...vacation,
  }));
}

export function appendVacationRow(
  rows: VacationTableRow[],
  employees: EmployeeTableRow[],
  fallbackDate: string,
): VacationTableRow[] {
  const employeeCode = employees[0]?.employeeCode ?? "E001";
  return [
    ...rows,
    {
      id: nextRowId("vacation", rows),
      employeeCode,
      startDate: fallbackDate,
      endDate: fallbackDate,
      type: "vacation",
      overrideAllowed: true,
    },
  ];
}

export function removeVacationRow(rows: VacationTableRow[], rowId: string): VacationTableRow[] {
  if (rows.length <= 1) return rows;
  return rows.filter((row) => row.id !== rowId);
}

export function updateVacationRow(
  rows: VacationTableRow[],
  rowId: string,
  patch: Partial<Omit<VacationTableRow, "id">>,
): VacationTableRow[] {
  return rows.map((row) => (row.id === rowId ? normalizeVacationRow({ ...row, ...patch }) : row));
}

export function vacationRowsToDrafts(rows: VacationTableRow[]): VacationDraft[] {
  return rows.map((row) => {
    const normalized = normalizeVacationRow(row);
    return {
      employeeCode: normalized.employeeCode,
      startDate: normalized.startDate,
      endDate: normalized.endDate,
      type: normalized.type || "vacation",
      overrideAllowed: normalized.overrideAllowed,
    };
  });
}

export function normalizeVacationRowsForEmployees(
  rows: VacationTableRow[],
  employees: EmployeeTableRow[],
): VacationTableRow[] {
  const employeeCodes = new Set(employees.map((employee) => employee.employeeCode));
  const fallbackEmployeeCode = employees[0]?.employeeCode ?? "E001";
  return rows.map((row) =>
    employeeCodes.has(row.employeeCode)
      ? normalizeVacationRow(row)
      : normalizeVacationRow({ ...row, employeeCode: fallbackEmployeeCode }),
  );
}

export function buildPairTableRows(config: ScenarioConfig): PairTableRow[] {
  return buildDefaultPairDrafts(config).map((pair, index) => ({
    id: `pair-${index + 1}`,
    ...pair,
  }));
}

export function appendPairRow(rows: PairTableRow[], employees: EmployeeTableRow[]): PairTableRow[] {
  const [employeeA, employeeB] = nextAvailablePairCodes(rows, employees);
  return [
    ...rows,
    {
      id: nextRowId("pair", rows),
      employeeACode: employeeA,
      employeeBCode: employeeB,
      severity: "high",
      overrideAllowed: true,
    },
  ];
}

export function removePairRow(rows: PairTableRow[], rowId: string): PairTableRow[] {
  if (rows.length <= 1) return rows;
  return rows.filter((row) => row.id !== rowId);
}

export function updatePairRow(
  rows: PairTableRow[],
  rowId: string,
  patch: Partial<Omit<PairTableRow, "id">>,
  employees: EmployeeTableRow[],
): PairTableRow[] {
  return rows.map((row) =>
    row.id === rowId ? normalizePairRow({ ...row, ...patch }, employees) : row,
  );
}

export function pairRowsToDrafts(rows: PairTableRow[]): PairDraft[] {
  return rows.map((row) => ({
    employeeACode: row.employeeACode,
    employeeBCode: row.employeeBCode,
    severity: row.severity || "high",
    overrideAllowed: row.overrideAllowed,
  }));
}

export function normalizePairRowsForEmployees(
  rows: PairTableRow[],
  employees: EmployeeTableRow[],
): PairTableRow[] {
  return rows.map((row) => normalizePairRow(row, employees));
}

function employeeToTableRow(employee: ScenarioDraftEmployee): EmployeeTableRow {
  return {
    id: `employee-${employee.employeeCode}`,
    employeeCode: employee.employeeCode,
    name: employee.name,
    roleNames: normalizeRoleNames(employee.roleNames),
    maxShiftsPerWeek: employee.maxShiftsPerWeek,
  };
}

function normalizeRoleNames(roleNames: string[]): string[] {
  const selected = new Set(roleNames.filter((roleName) => ROLE_OPTIONS.includes(roleName as never)));
  const normalized = ROLE_OPTIONS.filter((roleName) => selected.has(roleName));
  return normalized.length ? normalized : [ROLE_OPTIONS[0]];
}

function normalizePositiveInteger(value: number, fallback: number): number {
  return Number.isInteger(value) && value > 0 ? value : fallback;
}

function normalizeVacationRow(row: VacationTableRow): VacationTableRow {
  return {
    ...row,
    endDate: row.endDate >= row.startDate ? row.endDate : row.startDate,
    type: row.type || "vacation",
  };
}

function normalizePairRow(row: PairTableRow, employees: EmployeeTableRow[]): PairTableRow {
  const employeeCodes = employees.map((employee) => employee.employeeCode);
  const [fallbackA, fallbackB] = firstTwoEmployeeCodes(employees);
  const employeeACode = employeeCodes.includes(row.employeeACode) ? row.employeeACode : fallbackA;
  const employeeBCode =
    employeeCodes.includes(row.employeeBCode) && row.employeeBCode !== employeeACode
      ? row.employeeBCode
      : employeeCodes.find((employeeCode) => employeeCode !== employeeACode) ?? fallbackB;
  return {
    ...row,
    employeeACode,
    employeeBCode,
    severity: row.severity || "high",
  };
}

function firstTwoEmployeeCodes(employees: EmployeeTableRow[]): [string, string] {
  const employeeA = employees[0]?.employeeCode ?? "E001";
  const employeeB = employees.find((employee) => employee.employeeCode !== employeeA)?.employeeCode ?? "E002";
  return [employeeA, employeeB];
}

function nextAvailablePairCodes(rows: PairTableRow[], employees: EmployeeTableRow[]): [string, string] {
  const employeeCodes = employees.map((employee) => employee.employeeCode);
  const usedPairs = new Set(
    rows.map((row) => normalizedPairKey(row.employeeACode, row.employeeBCode)),
  );
  for (let index = 0; index < employeeCodes.length - 1; index += 2) {
    const employeeA = employeeCodes[index];
    const employeeB = employeeCodes[index + 1];
    if (!usedPairs.has(normalizedPairKey(employeeA, employeeB))) {
      return [employeeA, employeeB];
    }
  }
  for (const employeeA of employeeCodes) {
    const employeeB = employeeCodes.find(
      (candidate) => candidate !== employeeA && !usedPairs.has(normalizedPairKey(employeeA, candidate)),
    );
    if (employeeB) return [employeeA, employeeB];
  }
  return firstTwoEmployeeCodes(employees);
}

function normalizedPairKey(employeeACode: string, employeeBCode: string): string {
  return [employeeACode, employeeBCode].sort().join("|");
}

function nextRowId(prefix: string, rows: { id: string }[]): string {
  const nextNumber =
    rows.reduce((currentMax, row) => {
      const match = new RegExp(`^${prefix}-(\\d+)$`).exec(row.id);
      return match ? Math.max(currentMax, Number(match[1])) : currentMax;
    }, 0) + 1;
  return `${prefix}-${nextNumber}`;
}

function employeeCodeFor(employeeNumber: number): string {
  return `E${employeeNumber.toString().padStart(3, "0")}`;
}
