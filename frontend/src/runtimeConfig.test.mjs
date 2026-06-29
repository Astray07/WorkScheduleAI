import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-runtime-config-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before runtime config tests.");
}

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

try {
  execFileSync(
    process.execPath,
    [
      tscBin,
      "--target",
      "ES2022",
      "--module",
      "NodeNext",
      "--moduleResolution",
      "NodeNext",
      "--rootDir",
      join(projectRoot, "src"),
      "--outDir",
      outDir,
      join(projectRoot, "src", "runtimeConfig.ts"),
    ],
    { stdio: "inherit" },
  );

  const { resolveRuntimeConfig } = await import(
    pathToFileURL(join(outDir, "runtimeConfig.js")).href
  );

  assert.deepEqual(
    resolveRuntimeConfig({
      DEV: true,
      PROD: false,
      VITE_API_BASE_URL: undefined,
    }),
    {
      apiBase: "http://127.0.0.1:8000",
      configurationError: null,
    },
  );
  assert.deepEqual(
    resolveRuntimeConfig({
      DEV: false,
      PROD: true,
      VITE_API_BASE_URL: undefined,
    }),
    {
      apiBase: "",
      configurationError:
        "배포 설정 오류: VITE_API_BASE_URL이 설정되지 않았습니다. Railway 프론트 서비스 변수에 API URL을 추가해주세요.",
    },
  );
  assert.deepEqual(
    resolveRuntimeConfig({
      DEV: false,
      PROD: true,
      VITE_API_BASE_URL: "https://api.example.com/",
    }),
    {
      apiBase: "https://api.example.com",
      configurationError: null,
    },
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
