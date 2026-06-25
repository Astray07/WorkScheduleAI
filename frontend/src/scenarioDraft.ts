export type ScenarioDraftEmployee = {
  rowNo: number;
  employeeCode: string;
  name: string;
  roleNames: string[];
  maxShiftsPerWeek: number;
};

export type VacationDraft = {
  employeeCode: string;
  startDate: string;
  endDate: string;
  type: string;
  overrideAllowed: boolean;
};

export type PairDraft = {
  employeeACode: string;
  employeeBCode: string;
  severity: string;
  overrideAllowed: boolean;
};

export type DraftSummaryInput = {
  employeeDraft: string;
  vacationDraft: string;
  pairDraft: string;
  periodDays: number;
};

export function parseEmployeeDraft(text: string): ScenarioDraftEmployee[] {
  const seen = new Set<string>();
  return nonEmptyLines(text).map((line, index) => {
    const [employeeCode, name, roles, maxShiftsPerWeek] = splitDraftLine(line);
    if (!employeeCode || !isEmployeeCode(employeeCode)) {
      throw new Error(`Invalid employee_code at row ${index + 1}.`);
    }
    if (seen.has(employeeCode)) {
      throw new Error(`Duplicate employee_code ${employeeCode}.`);
    }
    seen.add(employeeCode);
    if (!name) {
      throw new Error(`Missing employee name at row ${index + 1}.`);
    }
    const roleNames = roles
      ? roles.split("|").map((role) => role.trim()).filter(Boolean)
      : [];
    if (!roleNames.length) {
      throw new Error(`Missing role_names at row ${index + 1}.`);
    }
    return {
      rowNo: index + 1,
      employeeCode,
      name,
      roleNames,
      maxShiftsPerWeek: parsePositiveInteger(maxShiftsPerWeek, 5, `max_shifts_per_week at row ${index + 1}`),
    };
  });
}

export function parseVacationDraft(text: string): VacationDraft[] {
  return nonEmptyLines(text).map((line, index) => {
    const [employeeCode, startDate, third, fourth, fifth] = splitDraftLine(line);
    if (!employeeCode || !isEmployeeCode(employeeCode)) {
      throw new Error(`Invalid vacation employee_code at row ${index + 1}.`);
    }
    if (!isIsoDate(startDate)) {
      throw new Error(`Invalid vacation start_date at row ${index + 1}.`);
    }
    const rangeRow = isIsoDate(third);
    const endDate = rangeRow ? third : startDate;
    const type = rangeRow ? fourth : third;
    const overrideAllowed = rangeRow ? fifth : fourth;
    if (endDate < startDate) {
      throw new Error(`Vacation end_date must be on or after start_date at row ${index + 1}.`);
    }
    return {
      employeeCode,
      startDate,
      endDate,
      type: type || "vacation",
      overrideAllowed: parseBoolean(overrideAllowed, true, `override_allowed at row ${index + 1}`),
    };
  });
}

export function parsePairDraft(text: string): PairDraft[] {
  return nonEmptyLines(text).map((line, index) => {
    const [employeeACode, employeeBCode, severity, overrideAllowed] = splitDraftLine(line);
    if (!employeeACode || !isEmployeeCode(employeeACode)) {
      throw new Error(`Invalid pair employee_a_code at row ${index + 1}.`);
    }
    if (!employeeBCode || !isEmployeeCode(employeeBCode)) {
      throw new Error(`Invalid pair employee_b_code at row ${index + 1}.`);
    }
    if (employeeACode === employeeBCode) {
      throw new Error(`Pair employees must be different at row ${index + 1}.`);
    }
    return {
      employeeACode,
      employeeBCode,
      severity: severity || "high",
      overrideAllowed: parseBoolean(overrideAllowed, true, `override_allowed at row ${index + 1}`),
    };
  });
}

export function formatEmployeeDraft(employees: ScenarioDraftEmployee[]): string {
  return employees
    .map((employee) =>
      [
        employee.employeeCode,
        employee.name,
        employee.roleNames.join("|"),
        employee.maxShiftsPerWeek.toString(),
      ].join(","),
    )
    .join("\n");
}

export function formatVacationDraft(vacations: VacationDraft[]): string {
  return vacations
    .map((vacation) =>
      [
        vacation.employeeCode,
        vacation.startDate,
        vacation.endDate,
        vacation.type || "vacation",
        vacation.overrideAllowed ? "true" : "false",
      ].join(","),
    )
    .join("\n");
}

export function formatPairDraft(pairs: PairDraft[]): string {
  return pairs
    .map((pair) =>
      [
        pair.employeeACode,
        pair.employeeBCode,
        pair.severity || "high",
        pair.overrideAllowed ? "true" : "false",
      ].join(","),
    )
    .join("\n");
}

export function buildDraftSummary(input: DraftSummaryInput): string {
  return `직원 ${countDraftRows(input.employeeDraft)}명, 휴가 ${countDraftRows(input.vacationDraft)}건, 상극 ${countDraftRows(input.pairDraft)}건, ${input.periodDays}일 생성`;
}

function nonEmptyLines(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function splitDraftLine(line: string): string[] {
  return line.split(",").map((part) => part.trim());
}

function countDraftRows(text: string): number {
  return nonEmptyLines(text).length;
}

function isEmployeeCode(value: string): boolean {
  return /^E\d{3}$/.test(value);
}

function isIsoDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function parsePositiveInteger(value: string | undefined, defaultValue: number, label: string): number {
  if (!value) return defaultValue;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`Invalid ${label}.`);
  }
  return parsed;
}

function parseBoolean(value: string | undefined, defaultValue: boolean, label: string): boolean {
  if (!value) return defaultValue;
  const normalized = value.toLowerCase();
  if (["true", "yes", "1"].includes(normalized)) return true;
  if (["false", "no", "0"].includes(normalized)) return false;
  throw new Error(`Invalid ${label}.`);
}
