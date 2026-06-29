type RuntimeEnv = {
  DEV: boolean;
  PROD: boolean;
  VITE_API_BASE_URL?: string;
};

type RuntimeConfig = {
  apiBase: string;
  configurationError: string | null;
};

const DEVELOPMENT_API_BASE = "http://127.0.0.1:8000";
const MISSING_API_BASE_MESSAGE =
  "배포 설정 오류: VITE_API_BASE_URL이 설정되지 않았습니다. Railway 프론트 서비스 변수에 API URL을 추가해주세요.";

export function resolveRuntimeConfig(env: RuntimeEnv): RuntimeConfig {
  const configuredApiBase = env.VITE_API_BASE_URL?.trim();
  if (configuredApiBase) {
    return {
      apiBase: configuredApiBase.replace(/\/+$/, ""),
      configurationError: null,
    };
  }
  if (env.DEV) {
    return {
      apiBase: DEVELOPMENT_API_BASE,
      configurationError: null,
    };
  }
  return {
    apiBase: "",
    configurationError: MISSING_API_BASE_MESSAGE,
  };
}
