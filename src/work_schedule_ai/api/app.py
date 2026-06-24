from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from work_schedule_ai.api.routes.employees import router as employees_router
from work_schedule_ai.api.routes.organizations import router as organizations_router
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


def create_app() -> FastAPI:
    app = FastAPI(title="WorkScheduleAI")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

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
