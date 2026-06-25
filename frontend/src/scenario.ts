export const MIN_EMPLOYEE_COUNT = 4;
export const MAX_EMPLOYEE_COUNT = 50;
export const PERIOD_DAY_OPTIONS = [7, 14, 31] as const;

export type PeriodDays = (typeof PERIOD_DAY_OPTIONS)[number];

export type ScenarioConfig = {
  employeeCount: number;
  periodDays: number;
  startDate: string;
  vacationEmployeeCode: string;
  vacationDate: string;
  pairEmployeeACode: string;
  pairEmployeeBCode: string;
};

export type ScenarioEmployee = {
  rowNo: number;
  employeeCode: string;
  name: string;
  roleNames: string[];
  maxShiftsPerWeek: number;
};

const employeeNames = [
  "Kim",
  "Lee",
  "Park",
  "Choi",
  "Jung",
  "Kang",
  "Cho",
  "Yoon",
  "Jang",
  "Lim",
  "Han",
  "Oh",
  "Shin",
  "Seo",
  "Kwon",
  "Hwang",
  "Ahn",
  "Song",
  "Ryu",
  "Hong",
  "Moon",
  "Yang",
  "Baek",
  "Nam",
  "Ko",
  "Bae",
  "Jeon",
  "Ha",
  "Min",
  "Noh",
  "Joo",
  "Woo",
  "Son",
  "Cha",
  "Do",
  "Ji",
  "Won",
  "Gwak",
  "Pyo",
  "Bang",
  "Seok",
  "Ma",
  "Gil",
  "Ra",
  "Tak",
  "Mo",
  "Byun",
  "Yeo",
  "Geum",
  "Eom",
];

export const DEFAULT_SCENARIO_CONFIG: ScenarioConfig = {
  employeeCount: 12,
  periodDays: 14,
  startDate: "2026-07-01",
  vacationEmployeeCode: "E002",
  vacationDate: "2026-07-02",
  pairEmployeeACode: "E001",
  pairEmployeeBCode: "E002",
};

export function buildScenarioEmployees(count: number): ScenarioEmployee[] {
  const employeeCount = clampEmployeeCount(count);
  return Array.from({ length: employeeCount }, (_, index) => {
    const employeeNumber = index + 1;
    return {
      rowNo: employeeNumber,
      employeeCode: employeeCodeFor(employeeNumber),
      name: employeeNames[index] ?? `Employee ${employeeNumber}`,
      roleNames: roleNamesForIndex(index),
      maxShiftsPerWeek: 5,
    };
  });
}

export function normalizeScenarioConfig(config: ScenarioConfig): ScenarioConfig {
  const employeeCount = clampEmployeeCount(config.employeeCount);
  const periodDays = normalizePeriodDays(config.periodDays);
  const pairEmployeeACode = codeWithinRange(config.pairEmployeeACode, employeeCount)
    ? config.pairEmployeeACode
    : "E001";
  const fallbackPairBCode = nextEmployeeCode(pairEmployeeACode, employeeCount);
  const pairEmployeeBCode =
    codeWithinRange(config.pairEmployeeBCode, employeeCount) &&
    config.pairEmployeeBCode !== pairEmployeeACode
      ? config.pairEmployeeBCode
      : fallbackPairBCode;

  return {
    ...config,
    employeeCount,
    periodDays,
    vacationEmployeeCode: codeWithinRange(config.vacationEmployeeCode, employeeCount)
      ? config.vacationEmployeeCode
      : employeeCodeFor(Math.min(2, employeeCount)),
    pairEmployeeACode,
    pairEmployeeBCode,
  };
}

export function addDaysIso(isoDate: string, days: number): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) return isoDate;
  const [, year, month, day] = match;
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function periodEndFor(startDate: string, periodDays: number): string {
  return addDaysIso(startDate, normalizePeriodDays(periodDays) - 1);
}

export function buildScenarioSummary(config: ScenarioConfig): string {
  const normalized = normalizeScenarioConfig(config);
  return `직원 ${normalized.employeeCount}명, 휴가 ${normalized.vacationEmployeeCode}, 상극 ${normalized.pairEmployeeACode}/${normalized.pairEmployeeBCode}, ${normalized.periodDays}일 생성`;
}

function clampEmployeeCount(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_SCENARIO_CONFIG.employeeCount;
  return Math.min(MAX_EMPLOYEE_COUNT, Math.max(MIN_EMPLOYEE_COUNT, Math.trunc(value)));
}

function normalizePeriodDays(value: number): PeriodDays {
  if (value <= 7) return 7;
  if (value <= 14) return 14;
  return 31;
}

function roleNamesForIndex(index: number): string[] {
  if (index % 4 === 0) return ["사수"];
  if (index % 4 === 1) return ["부사수"];
  return ["사수", "부사수"];
}

function employeeCodeFor(employeeNumber: number): string {
  return `E${employeeNumber.toString().padStart(3, "0")}`;
}

function codeWithinRange(code: string, employeeCount: number): boolean {
  const match = /^E(\d{3})$/.exec(code);
  if (!match) return false;
  const employeeNumber = Number(match[1]);
  return employeeNumber >= 1 && employeeNumber <= employeeCount;
}

function nextEmployeeCode(currentCode: string, employeeCount: number): string {
  const match = /^E(\d{3})$/.exec(currentCode);
  const currentNumber = match ? Number(match[1]) : 1;
  const nextNumber = currentNumber >= employeeCount ? 1 : currentNumber + 1;
  return employeeCodeFor(nextNumber);
}
