from fastapi import FastAPI

from work_schedule_ai.api.routes.organizations import router as organizations_router
from work_schedule_ai.contracts import (
    fixture_names,
    load_openapi_contract,
    missing_core_schemas,
    missing_p0_paths,
)


def create_app() -> FastAPI:
    app = FastAPI(title="WorkScheduleAI")
    app.include_router(organizations_router)

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
