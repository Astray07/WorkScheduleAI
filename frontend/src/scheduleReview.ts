import { dateDisplayLabel, slotDisplayLabel } from "./scenario.js";

export type ReviewSlot = {
  id: string;
  label: string;
  local_date: string;
};

export type ReviewRequirement = {
  role_id: string;
  role_name: string;
  slot_id: string;
};

export type ReviewIssue = {
  id: string;
  role_id: string | null;
  slot_id: string | null;
};

export type ReviewProposal = {
  affected_slot_id: string | null;
  impact_preview: {
    resolved_issue_ids: string[];
  };
};

export function issueContextLabel(
  issue: ReviewIssue,
  slots: ReviewSlot[],
  requirements: ReviewRequirement[],
): string {
  return contextLabel(issue.slot_id, issue.role_id, slots, requirements);
}

export function proposalContextLabel(
  proposal: ReviewProposal,
  issues: ReviewIssue[],
  slots: ReviewSlot[],
  requirements: ReviewRequirement[],
): string {
  const relatedIssue = issues.find((issue) =>
    proposal.impact_preview.resolved_issue_ids.includes(issue.id),
  );
  return contextLabel(
    proposal.affected_slot_id ?? relatedIssue?.slot_id ?? null,
    relatedIssue?.role_id ?? null,
    slots,
    requirements,
  );
}

function contextLabel(
  slotId: string | null,
  roleId: string | null,
  slots: ReviewSlot[],
  requirements: ReviewRequirement[],
): string {
  const slot = slots.find((candidate) => candidate.id === slotId);
  const roleName =
    slotId && roleId
      ? requirements.find(
          (requirement) =>
            requirement.slot_id === slotId && requirement.role_id === roleId,
        )?.role_name
      : null;
  if (!slot) return roleName ?? "일정 미지정";
  return [dateDisplayLabel(slot.local_date), slotDisplayLabel(slot.label, slot.local_date), roleName]
    .filter(Boolean)
    .join(" · ");
}
