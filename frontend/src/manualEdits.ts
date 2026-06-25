export type ManualEditEmployee = {
  id: string;
  name: string;
};

export type ManualEditAssignment = {
  id: string;
  slot_id: string;
  role_id: string;
  employee_id: string;
  employee_name?: string;
  source: string;
  locked_by_user: boolean;
};

export type ManualEditDraft = {
  slotId: string;
  roleId: string;
  employeeId: string;
  lockedByUser: boolean;
};

export type ManualEditRequest = {
  slot_id: string;
  role_id: string;
  employee_id: string;
  locked_by_user: boolean;
};

export function openManualEditDraft({
  assignment,
  employees,
  roleId,
  slotId,
}: {
  assignment?: ManualEditAssignment | null;
  employees: ManualEditEmployee[];
  roleId: string;
  slotId: string;
}): ManualEditDraft {
  return {
    slotId,
    roleId,
    employeeId: assignment?.employee_id ?? employees[0]?.id ?? "",
    lockedByUser: assignment?.locked_by_user ?? true,
  };
}

export function manualEditRequest(draft: ManualEditDraft): ManualEditRequest {
  return {
    slot_id: draft.slotId,
    role_id: draft.roleId,
    employee_id: draft.employeeId,
    locked_by_user: draft.lockedByUser,
  };
}

export function mergeSavedAssignment<T extends ManualEditAssignment>(
  assignments: T[],
  savedAssignment: T,
): T[] {
  const nextAssignments = assignments.filter(
    (assignment) =>
      assignment.slot_id !== savedAssignment.slot_id ||
      assignment.role_id !== savedAssignment.role_id,
  );
  return [...nextAssignments, savedAssignment];
}

export function assignmentSourceLabel(assignment: Pick<ManualEditAssignment, "source">): string {
  if (assignment.source === "manual") return "수동";
  if (assignment.source === "override") return "예외";
  return "자동";
}

export function assignmentLockLabel(
  assignment: Pick<ManualEditAssignment, "locked_by_user">,
): string {
  return assignment.locked_by_user ? "잠금" : "잠금 해제";
}
