import type { AuthSession } from "./authSession";

export type WorkspaceRole = {
  id: string;
  name: string;
};

export type OrganizationWorkspace = {
  id: string;
  default_roles: WorkspaceRole[];
};

export type ScenarioEmployeeSyncRow = {
  employee_code: string;
  name: string;
  role_names: string[];
  max_shifts_per_week: number;
};

export type ManagedEmployeeForSync = {
  active: boolean;
  employee_code: string;
  name: string;
  role_names: string[];
  max_shifts_per_week: number | null;
};

export function workspaceFromSession(
  session: Pick<AuthSession, "organization_id">,
  roles: WorkspaceRole[],
): OrganizationWorkspace {
  return {
    id: session.organization_id,
    default_roles: roles,
  };
}

export function shouldSyncScenarioEmployees(
  scenarioRows: ScenarioEmployeeSyncRow[],
  managedEmployees: ManagedEmployeeForSync[],
): boolean {
  const managedByCode = new Map(
    managedEmployees
      .filter((employee) => employee.active)
      .map((employee) => [employee.employee_code, employee]),
  );
  return scenarioRows.some((row) => {
    const managed = managedByCode.get(row.employee_code);
    if (!managed) return true;
    return (
      managed.name !== row.name ||
      (managed.max_shifts_per_week ?? 5) !== row.max_shifts_per_week ||
      normalizedRoles(managed.role_names).join("|") !==
        normalizedRoles(row.role_names).join("|")
    );
  });
}

function normalizedRoles(roleNames: string[]): string[] {
  return [...new Set(roleNames)].sort();
}
