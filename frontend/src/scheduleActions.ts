type RecalculationProposal = {
  status: string;
};

type RecalculationResult = {
  proposals: RecalculationProposal[];
};

export function canRecalculate(result: RecalculationResult | null): boolean {
  return result?.proposals.some((proposal) => proposal.status === "approved") ?? false;
}
