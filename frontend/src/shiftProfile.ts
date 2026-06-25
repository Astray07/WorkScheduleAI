export const SHIFT_PRESET_IDS = ["day", "morning", "afternoon", "night"] as const;
export const SHIFT_DAY_GROUPS = ["weekday", "weekend"] as const;

export type ShiftPresetId = (typeof SHIFT_PRESET_IDS)[number];
export type ShiftDayGroup = (typeof SHIFT_DAY_GROUPS)[number];

export type ShiftCoverage = Record<ShiftDayGroup, ShiftPresetId[]>;

export type RoleIds = {
  seniorRoleId: string;
  juniorRoleId: string;
};

export type ShiftTypeRequest = {
  name: string;
  local_start_time: string;
  local_end_time: string;
  timezone: string;
  crosses_midnight: boolean;
  active_weekdays: number[];
  requirements: { role_id: string; required_count: number }[];
};

export type ExistingShiftTypeForSync = ShiftTypeRequest & {
  id: string;
  active: boolean;
  requirements: {
    role_id: string;
    required_count: number;
    unfilled_weight_override?: number | null;
  }[];
};

export type ShiftTypeUpdateRequest = ShiftTypeRequest & {
  active: boolean;
};

export type ScenarioShiftTypeSyncPlan = {
  creates: ShiftTypeRequest[];
  updates: { id: string; request: ShiftTypeUpdateRequest }[];
};

type ShiftPreset = {
  id: ShiftPresetId;
  label: string;
  namePart: string;
  localStartTime: string;
  localEndTime: string;
  crossesMidnight: boolean;
};

type DayGroupPreset = {
  id: ShiftDayGroup;
  label: string;
  weekdays: number[];
};

export const DEFAULT_SHIFT_COVERAGE: ShiftCoverage = {
  weekday: ["morning", "afternoon"],
  weekend: ["day"],
};

export const SHIFT_PRESETS: ShiftPreset[] = [
  {
    id: "day",
    label: "주간",
    namePart: "주간",
    localStartTime: "09:00",
    localEndTime: "18:00",
    crossesMidnight: false,
  },
  {
    id: "morning",
    label: "오전",
    namePart: "오전",
    localStartTime: "06:00",
    localEndTime: "14:00",
    crossesMidnight: false,
  },
  {
    id: "afternoon",
    label: "오후",
    namePart: "오후",
    localStartTime: "14:00",
    localEndTime: "22:00",
    crossesMidnight: false,
  },
  {
    id: "night",
    label: "야간",
    namePart: "야간",
    localStartTime: "22:00",
    localEndTime: "06:00",
    crossesMidnight: true,
  },
];

export const SHIFT_DAY_GROUP_OPTIONS: DayGroupPreset[] = [
  { id: "weekday", label: "평일", weekdays: [0, 1, 2, 3, 4] },
  { id: "weekend", label: "주말", weekdays: [5, 6] },
];

export function normalizeShiftCoverage(coverage: ShiftCoverage): ShiftCoverage {
  const normalized: ShiftCoverage = {
    weekday: normalizeShiftIds(coverage.weekday),
    weekend: normalizeShiftIds(coverage.weekend),
  };
  if (!normalized.weekday.length && !normalized.weekend.length) {
    return cloneCoverage(DEFAULT_SHIFT_COVERAGE);
  }
  return normalized;
}

export function setShiftCoverageEnabled(
  coverage: ShiftCoverage,
  dayGroup: ShiftDayGroup,
  shiftId: ShiftPresetId,
  enabled: boolean,
): ShiftCoverage {
  const normalized = normalizeShiftCoverageAllowEmpty(coverage);
  const current = new Set(normalized[dayGroup]);
  if (enabled) {
    current.add(shiftId);
  } else {
    current.delete(shiftId);
  }
  return {
    ...normalized,
    [dayGroup]: normalizeShiftIds(Array.from(current)),
  };
}

export function buildShiftTypeRequests(
  coverage: ShiftCoverage,
  roleIds: RoleIds,
): ShiftTypeRequest[] {
  const normalized = normalizeShiftCoverage(coverage);
  const requests: ShiftTypeRequest[] = [];
  for (const dayGroup of SHIFT_DAY_GROUP_OPTIONS) {
    for (const shiftId of normalized[dayGroup.id]) {
      const preset = presetById(shiftId);
      requests.push({
        name: `${dayGroup.label} ${preset.namePart} 근무`,
        local_start_time: preset.localStartTime,
        local_end_time: preset.localEndTime,
        timezone: "Asia/Seoul",
        crosses_midnight: preset.crossesMidnight,
        active_weekdays: dayGroup.weekdays,
        requirements: [
          { role_id: roleIds.seniorRoleId, required_count: 1 },
          { role_id: roleIds.juniorRoleId, required_count: 1 },
        ],
      });
    }
  }
  return requests;
}

export function planScenarioShiftTypeSync(
  coverage: ShiftCoverage,
  roleIds: RoleIds,
  existingShiftTypes: ExistingShiftTypeForSync[],
): ScenarioShiftTypeSyncPlan {
  const desiredRequests = buildShiftTypeRequests(coverage, roleIds);
  const allScenarioRequests = buildShiftTypeRequests(
    {
      weekday: [...SHIFT_PRESET_IDS],
      weekend: [...SHIFT_PRESET_IDS],
    },
    roleIds,
  );
  const existingByName = new Map(existingShiftTypes.map((shiftType) => [shiftType.name, shiftType]));
  const desiredByName = new Map(desiredRequests.map((request) => [request.name, request]));
  const allScenarioByName = new Map(allScenarioRequests.map((request) => [request.name, request]));
  const creates: ShiftTypeRequest[] = [];
  const updates: { id: string; request: ShiftTypeUpdateRequest }[] = [];

  for (const request of desiredRequests) {
    const existing = existingByName.get(request.name);
    if (!existing) {
      creates.push(request);
      continue;
    }
    updates.push({
      id: existing.id,
      request: {
        ...request,
        active: true,
      },
    });
  }

  for (const existing of existingShiftTypes) {
    if (desiredByName.has(existing.name)) continue;
    const scenarioRequest = allScenarioByName.get(existing.name);
    if (!scenarioRequest || !existing.active) continue;
    updates.push({
      id: existing.id,
      request: {
        ...scenarioRequest,
        active: false,
      },
    });
  }

  return { creates, updates };
}

export function shiftCoverageSummary(coverage: ShiftCoverage): string {
  const normalized = normalizeShiftCoverage(coverage);
  return SHIFT_DAY_GROUP_OPTIONS
    .map((dayGroup) => {
      const labels = normalized[dayGroup.id].map((shiftId) => presetById(shiftId).label);
      return labels.length ? `${dayGroup.label} ${labels.join("/")}` : "";
    })
    .filter(Boolean)
    .join(", ");
}

function normalizeShiftCoverageAllowEmpty(coverage: ShiftCoverage): ShiftCoverage {
  return {
    weekday: normalizeShiftIds(coverage.weekday),
    weekend: normalizeShiftIds(coverage.weekend),
  };
}

function normalizeShiftIds(shiftIds: ShiftPresetId[]): ShiftPresetId[] {
  const allowed = new Set<ShiftPresetId>(SHIFT_PRESET_IDS);
  const selected = new Set<ShiftPresetId>();
  shiftIds.forEach((shiftId) => {
    if (allowed.has(shiftId)) {
      selected.add(shiftId);
    }
  });
  return SHIFT_PRESET_IDS.filter((shiftId) => selected.has(shiftId));
}

function presetById(shiftId: ShiftPresetId): ShiftPreset {
  return SHIFT_PRESETS.find((preset) => preset.id === shiftId) ?? SHIFT_PRESETS[0];
}

function cloneCoverage(coverage: ShiftCoverage): ShiftCoverage {
  return {
    weekday: [...coverage.weekday],
    weekend: [...coverage.weekend],
  };
}
