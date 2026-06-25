export const MIN_EMPLOYEE_COUNT = 4;
export const MAX_EMPLOYEE_COUNT = 50;
export const PERIOD_DAY_OPTIONS = [7, 14, 31] as const;

export type PeriodDays = (typeof PERIOD_DAY_OPTIONS)[number];

export type ScenarioConfig = {
  employeeCount: number;
  organizationName: string;
  periodDays: number;
  startDate: string;
  vacationEmployeeCode: string;
  vacationDate: string;
  vacationEndDate: string;
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

export type DefaultVacationDraft = {
  employeeCode: string;
  startDate: string;
  endDate: string;
  type: string;
  overrideAllowed: boolean;
};

const employeeNames = [
  "김민준",
  "이서연",
  "박지훈",
  "최하은",
  "정도윤",
  "강지우",
  "조현우",
  "윤서아",
  "장민서",
  "임하준",
  "한유진",
  "오수빈",
  "신지민",
  "서준호",
  "권예린",
  "황도현",
  "안시우",
  "송채원",
  "류지호",
  "홍나윤",
  "문서준",
  "양하린",
  "백건우",
  "남예준",
  "고아린",
  "배시윤",
  "전유나",
  "하지원",
  "민준서",
  "노서현",
  "주하율",
  "우민재",
  "손예나",
  "차은호",
  "도윤재",
  "지수아",
  "원태준",
  "곽서윤",
  "표지완",
  "방하영",
  "석민성",
  "마유림",
  "길도겸",
  "라예솔",
  "탁시현",
  "모은서",
  "변하민",
  "여주원",
  "금채린",
  "엄도하",
];

const koreanWeekdays = ["일", "월", "화", "수", "목", "금", "토"] as const;

export const DEFAULT_SCENARIO_CONFIG: ScenarioConfig = {
  employeeCount: 12,
  organizationName: "하나케어 운영팀",
  periodDays: 31,
  startDate: "2026-07-01",
  vacationEmployeeCode: "E002",
  vacationDate: "2026-07-02",
  vacationEndDate: "2026-07-04",
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
    organizationName: (config.organizationName ?? "").trim() || DEFAULT_SCENARIO_CONFIG.organizationName,
    periodDays,
    vacationEmployeeCode: codeWithinRange(config.vacationEmployeeCode, employeeCount)
      ? config.vacationEmployeeCode
      : employeeCodeFor(Math.min(2, employeeCount)),
    vacationEndDate:
      config.vacationEndDate >= config.vacationDate
        ? config.vacationEndDate
        : config.vacationDate,
    pairEmployeeACode,
    pairEmployeeBCode,
  };
}

export function buildDefaultVacationDrafts(config: ScenarioConfig): DefaultVacationDraft[] {
  const normalized = normalizeScenarioConfig(config);
  const employeeCodes = distinctEmployeeCodes(
    [2, 7, 10].map((employeeNumber) => Math.min(employeeNumber, normalized.employeeCount)),
    normalized.employeeCount,
  );
  const maxOffset = Math.max(0, normalized.periodDays - 1);
  return [
    {
      employeeCode: employeeCodes[0],
      startDate: addDaysIso(normalized.startDate, Math.min(1, maxOffset)),
      endDate: addDaysIso(normalized.startDate, Math.min(3, maxOffset)),
      type: "vacation",
      overrideAllowed: true,
    },
    {
      employeeCode: employeeCodes[1],
      startDate: addDaysIso(normalized.startDate, Math.min(14, maxOffset)),
      endDate: addDaysIso(normalized.startDate, Math.min(16, maxOffset)),
      type: "vacation",
      overrideAllowed: true,
    },
    {
      employeeCode: employeeCodes[2],
      startDate: addDaysIso(normalized.startDate, Math.min(19, maxOffset)),
      endDate: addDaysIso(normalized.startDate, Math.min(19, maxOffset)),
      type: "personal",
      overrideAllowed: true,
    },
  ];
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

export function dateDisplayLabel(isoDate: string): string {
  const weekday = weekdayLabel(isoDate);
  return weekday ? `${isoDate} (${weekday})` : isoDate;
}

export function dayTypeLabel(isoDate: string): string {
  const day = utcDayOfWeek(isoDate);
  if (day === null) return "날짜 확인";
  return day === 0 || day === 6 ? "주말" : "평일";
}

export function slotDisplayLabel(slotLabel: string, isoDate: string): string {
  return `${slotLabel} · ${dayTypeLabel(isoDate)}`;
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

function distinctEmployeeCodes(preferredNumbers: number[], employeeCount: number): string[] {
  const used = new Set<number>();
  return preferredNumbers.map((preferredNumber) => {
    let employeeNumber = Math.min(Math.max(preferredNumber, 1), employeeCount);
    if (used.has(employeeNumber)) {
      for (let candidate = 1; candidate <= employeeCount; candidate += 1) {
        if (!used.has(candidate)) {
          employeeNumber = candidate;
          break;
        }
      }
    }
    used.add(employeeNumber);
    return employeeCodeFor(employeeNumber);
  });
}

function weekdayLabel(isoDate: string): string | null {
  const day = utcDayOfWeek(isoDate);
  return day === null ? null : koreanWeekdays[day];
}

function utcDayOfWeek(isoDate: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) return null;
  const [, year, month, day] = match;
  return new Date(Date.UTC(Number(year), Number(month) - 1, Number(day))).getUTCDay();
}
