from __future__ import annotations

import os

SOLVER_POLICY_VERSION = "weekly_cap_fairness_v1"


def build_info() -> dict[str, str | None]:
    return {
        "app_env": os.environ.get("APP_ENV"),
        "railway_environment": os.environ.get("RAILWAY_ENVIRONMENT_NAME"),
        "railway_service": os.environ.get("RAILWAY_SERVICE_NAME"),
        "railway_deployment_id": os.environ.get("RAILWAY_DEPLOYMENT_ID"),
        "git_commit": _first_present_env(
            "RAILWAY_GIT_COMMIT_SHA",
            "SOURCE_COMMIT",
            "GIT_COMMIT_SHA",
        ),
        "git_branch": _first_present_env("RAILWAY_GIT_BRANCH", "GIT_BRANCH"),
        "solver_policy_version": SOLVER_POLICY_VERSION,
    }


def _first_present_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None
