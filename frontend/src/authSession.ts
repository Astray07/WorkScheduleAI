export type AuthSession = {
  access_token: string;
  expires_at?: string;
  organization_id: string;
  role: string;
  token_type?: string;
  user_id: string;
};

export type SessionIdentity = Pick<AuthSession, "organization_id" | "role" | "user_id">;

export function authHeaders(session: Pick<AuthSession, "access_token"> | null): Record<string, string> {
  if (!session?.access_token) return {};
  return { Authorization: `Bearer ${session.access_token}` };
}

export function sessionLabel(session: SessionIdentity | null): string {
  if (!session) return "로그인 필요";
  return `${session.organization_id} · ${session.role}`;
}

export function sessionVerificationPath(session: Pick<AuthSession, "organization_id">): string {
  return `/auth/session?organization_id=${encodeURIComponent(session.organization_id)}`;
}
