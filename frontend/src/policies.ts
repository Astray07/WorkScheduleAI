export type SchedulePolicy = {
  id?: string;
  organization_id?: string;
  name: string;
  min_rest_hours: number;
  max_consecutive_shifts: number;
  max_shifts_per_week: number;
  weekend_shift_limit_per_month: number;
  night_shift_limit_per_month: number;
  default_unfilled_requirement_weight: number;
  weight_workload_imbalance: number;
  weight_pair_avoid_violation: number;
  unfilled_policy: "soft_penalty";
};

export const DEFAULT_POLICY: SchedulePolicy = {
  name: "기본 정책",
  min_rest_hours: 11,
  max_consecutive_shifts: 5,
  max_shifts_per_week: 5,
  weekend_shift_limit_per_month: 4,
  night_shift_limit_per_month: 6,
  default_unfilled_requirement_weight: 900,
  weight_workload_imbalance: 100,
  weight_pair_avoid_violation: 60,
  unfilled_policy: "soft_penalty",
};

export function normalizePolicy(policy: Partial<SchedulePolicy> | null | undefined): SchedulePolicy {
  const merged = { ...DEFAULT_POLICY, ...(policy ?? {}) };
  return {
    ...merged,
    min_rest_hours: clampInteger(merged.min_rest_hours, 0, 48),
    max_consecutive_shifts: clampInteger(merged.max_consecutive_shifts, 1, 31),
    max_shifts_per_week: clampInteger(merged.max_shifts_per_week, 1, 14),
    weekend_shift_limit_per_month: clampInteger(merged.weekend_shift_limit_per_month, 0, 31),
    night_shift_limit_per_month: clampInteger(merged.night_shift_limit_per_month, 0, 31),
    default_unfilled_requirement_weight: clampInteger(
      merged.default_unfilled_requirement_weight,
      0,
      10000,
    ),
    weight_workload_imbalance: clampInteger(merged.weight_workload_imbalance, 0, 10000),
    weight_pair_avoid_violation: clampInteger(merged.weight_pair_avoid_violation, 0, 10000),
    unfilled_policy: "soft_penalty",
  };
}

export function unfilledPolicyLabel(policy: SchedulePolicy["unfilled_policy"]): string {
  return policy === "soft_penalty" ? "미배정 soft penalty" : policy;
}

function clampInteger(value: number, min: number, max: number): number {
  const integer = Number.isInteger(value) ? value : min;
  return Math.min(max, Math.max(min, integer));
}
