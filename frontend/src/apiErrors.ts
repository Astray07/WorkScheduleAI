type StructuredErrorDetail = {
  code?: unknown;
  message?: unknown;
};

const ERROR_MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: "이메일, 비밀번호 또는 조직 ID를 확인해주세요.",
  ORGANIZATION_ACCESS_DENIED: "이 조직에 접근할 권한이 없습니다.",
  SIGNED_ACTOR_SECRET_REQUIRED: "로그인 기능 설정이 완료되지 않았습니다. 관리자에게 문의해주세요.",
  SIGNED_ACTOR_SECRET_WEAK: "로그인 기능 설정이 완료되지 않았습니다. 관리자에게 문의해주세요.",
  PUBLICATION_PERIOD_OVERLAP:
    "같은 기간에 이미 확정된 근무표가 있습니다. 현재 근무표로 다시 확정하려면 기존 확정본을 보관 처리해야 합니다.",
};

export function apiErrorMessage(status: number, responseText: string): string {
  const detail = parseDetail(responseText);
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const code = stringValue((detail as StructuredErrorDetail).code);
    if (code && ERROR_MESSAGES[code]) {
      return ERROR_MESSAGES[code];
    }
    const message = stringValue((detail as StructuredErrorDetail).message);
    if (message && isSafeUserMessage(message)) {
      return message;
    }
  }
  if (status === 401) return "로그인 정보가 올바르지 않습니다.";
  if (status === 403) return "요청한 작업을 수행할 권한이 없습니다.";
  if (status === 404) return "요청한 데이터를 찾을 수 없습니다.";
  if (status === 409) return "현재 상태에서는 요청을 처리할 수 없습니다.";
  if (status === 422) return "입력값을 확인해주세요.";
  if (status >= 500) {
    return "서버에서 요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.";
  }
  return "요청을 처리하지 못했습니다.";
}

function parseDetail(responseText: string): unknown {
  if (!responseText) return null;
  try {
    const parsed = JSON.parse(responseText) as { detail?: unknown };
    return parsed.detail ?? parsed;
  } catch {
    return responseText;
  }
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function isSafeUserMessage(message: string): boolean {
  return !/[A-Z][A-Z0-9_]{8,}/.test(message);
}
