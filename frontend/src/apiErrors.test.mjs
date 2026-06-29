import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");
const outDir = join(tmpdir(), `workscheduleai-api-errors-test-${process.pid}`);
const tscBin = join(projectRoot, "node_modules", "typescript", "bin", "tsc");

if (!existsSync(tscBin)) {
  throw new Error("Run npm install in frontend before API error tests.");
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
      join(projectRoot, "src", "apiErrors.ts"),
    ],
    { stdio: "inherit" },
  );

  const { apiErrorMessage } = await import(pathToFileURL(join(outDir, "apiErrors.js")).href);

  assert.equal(
    apiErrorMessage(
      503,
      JSON.stringify({
        detail: {
          code: "SIGNED_ACTOR_SECRET_REQUIRED",
          message: "Login sessions require WORKSCHEDULEAI_SIGNED_ACTOR_SECRET.",
        },
      }),
    ),
    "로그인 기능 설정이 완료되지 않았습니다. 관리자에게 문의해주세요.",
  );
  assert.equal(
    apiErrorMessage(
      401,
      JSON.stringify({
        detail: {
          code: "INVALID_CREDENTIALS",
          message: "Email or password is invalid.",
        },
      }),
    ),
    "이메일, 비밀번호 또는 조직 ID를 확인해주세요.",
  );
  assert.equal(
    apiErrorMessage(503, JSON.stringify({ detail: "database unavailable" })),
    "서버에서 요청을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.",
  );
  assert.equal(
    apiErrorMessage(
      409,
      JSON.stringify({
        detail: {
          code: "PUBLICATION_PERIOD_OVERLAP",
          message: "Published SchedulePublication period overlaps.",
        },
      }),
    ),
    "같은 기간에 이미 확정된 근무표가 있습니다. 현재 근무표로 다시 확정하려면 기존 확정본을 보관 처리해야 합니다.",
  );
} finally {
  rmSync(outDir, { recursive: true, force: true });
}
