import type { AuthSession } from "./authSession";

export type WorkspaceRole = {
  id: string;
  name: string;
};

export type OrganizationWorkspace = {
  id: string;
  default_roles: WorkspaceRole[];
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
