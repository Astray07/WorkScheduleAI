from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_railway_api_and_worker_start_commands_are_explicitly_separated():
    api_config = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    worker_config = json.loads(
        (ROOT / "railway.worker.json").read_text(encoding="utf-8")
    )

    api_start = api_config["deploy"]["startCommand"]
    worker_start = worker_config["deploy"]["startCommand"]

    assert "uvicorn work_schedule_ai.api.app:create_app" in api_start
    assert "work_schedule_ai.worker.queue_worker" in worker_start
    assert api_start != worker_start
