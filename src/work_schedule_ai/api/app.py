import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.api.routes.employees import router as employees_router
from work_schedule_ai.api.routes.organizations import router as organizations_router
from work_schedule_ai.api.routes.operations import router as operations_router
from work_schedule_ai.api.routes.pair_constraints import (
    router as pair_constraints_router,
)
from work_schedule_ai.api.routes.schedule_runs import router as schedule_runs_router
from work_schedule_ai.api.routes.shift_templates import router as shift_templates_router
from work_schedule_ai.api.routes.unavailabilities import (
    router as unavailabilities_router,
)
from work_schedule_ai.contracts import (
    fixture_names,
    load_openapi_contract,
    missing_core_schemas,
    missing_p0_paths,
)
from work_schedule_ai.version import build_info


def create_app() -> FastAPI:
    app = FastAPI(title="WorkScheduleAI")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allow_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(organizations_router)
    app.include_router(employees_router)
    app.include_router(unavailabilities_router)
    app.include_router(pair_constraints_router)
    app.include_router(shift_templates_router)
    app.include_router(schedule_runs_router)
    app.include_router(operations_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def readiness(db_session: Session = Depends(get_db_session)) -> dict[str, str]:
        db_session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "ok",
            "redis": _redis_readiness_status(),
        }

    @app.get("/health/version")
    async def version() -> dict[str, str | None]:
        return build_info()

    @app.get("/contracts/m0/summary")
    async def m0_contract_summary() -> dict[str, object]:
        contract = load_openapi_contract()
        schemas = contract.get("components", {}).get("schemas", {})
        return {
            "missing_paths": missing_p0_paths(contract),
            "missing_schemas": missing_core_schemas(contract),
            "path_count": len(contract.get("paths", {})),
            "schema_count": len(schemas),
            "fixture_names": fixture_names(),
        }

    return app


def _cors_allow_origins() -> list[str]:
    configured = os.environ.get("CORS_ALLOW_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def _redis_readiness_status() -> str:
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return "not_configured"
    try:
        from redis import Redis

        Redis.from_url(redis_url).ping()
    except Exception:
        return "error"
    return "ok"
