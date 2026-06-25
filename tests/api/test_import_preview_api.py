import base64
import html
import zipfile
from io import BytesIO
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.api.app import create_app
from work_schedule_ai.api.dependencies import get_db_session
from work_schedule_ai.db.models import Base, Employee, Organization, Role


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Organization(id="org_1", name="Demo Clinic", timezone="Asia/Seoul"))
        session.add(Organization(id="org_2", name="Other Clinic", timezone="Asia/Seoul"))
        session.add_all(
            [
                Role(id="role_senior", organization_id="org_1", name="사수"),
                Role(id="role_junior", organization_id="org_1", name="부사수"),
                Role(id="role_external", organization_id="org_2", name="외부역할"),
                Employee(
                    id="emp_1",
                    organization_id="org_1",
                    employee_code="E001",
                    name="Kim",
                ),
                Employee(
                    id="emp_2",
                    organization_id="org_1",
                    employee_code="E002",
                    name="Lee",
                ),
            ]
        )
        session.commit()
        yield session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_preview_employee_import_returns_rows_and_errors(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "employees",
            "content": (
                "employee_code,name,roles,max_shifts_per_week\n"
                "E001,Kim,사수,5\n"
                "E002,,부사수,5"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["rows"][0]["employee_code"] == "E001"
    assert payload["errors"][0]["row_no"] == 2
    assert payload["errors"][0]["field"] == "name"


def test_apply_employee_import_uses_bulk_upsert(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/apply",
        json={
            "type": "employees",
            "mode": "upsert",
            "content": (
                "employee_code,name,roles,max_shifts_per_week\n"
                "E003,Park,사수|부사수,5"
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    employees = client.get("/organizations/org_1/employees").json()
    assert [employee["employee_code"] for employee in employees] == [
        "E001",
        "E002",
        "E003",
    ]


def test_preview_employee_import_rejects_negative_weekly_cap(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "employees",
            "content": (
                "employee_code,name,roles,max_shifts_per_week\n"
                "E003,Park,사수,-1"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["errors"] == [
        {
            "field": "max_shifts_per_week",
            "row_no": 1,
            "code": "INVALID_RANGE",
            "message": "max_shifts_per_week must be between 0 and 31.",
        }
    ]


def test_apply_unavailability_import_uses_employee_code(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/apply",
        json={
            "type": "unavailabilities",
            "mode": "upsert",
            "content": (
                "employee_code,type,starts_at,ends_at,override_allowed\n"
                "E001,vacation,2026-07-01T00:00:00+09:00,2026-07-02T00:00:00+09:00,false"
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert client.get("/organizations/org_1/unavailabilities").json()[0]["employee_id"] == "emp_1"


def test_apply_pair_constraint_import_uses_employee_codes(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/apply",
        json={
            "type": "pair_constraints",
            "mode": "upsert",
            "content": (
                "employee_code_a,employee_code_b,type,severity,override_allowed\n"
                "E001,E002,blocked,high,true"
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert client.get("/organizations/org_1/pair-constraints").json()[0]["employee_a_id"] == "emp_1"


def test_preview_policy_import_parses_key_value_rows(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "policy",
            "content": "key,value\nmin_rest_hours,10\nmax_consecutive_shifts,4",
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_apply_policy_import_updates_policy(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/apply",
        json={
            "type": "policy",
            "mode": "upsert",
            "content": "key\tvalue\nmin_rest_hours\t10\nmax_consecutive_shifts\t4",
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    policy = client.get("/organizations/org_1/schedule-policy").json()
    assert policy["min_rest_hours"] == 10
    assert policy["max_consecutive_shifts"] == 4


def test_preview_policy_import_rejects_values_outside_api_contract(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "policy",
            "content": (
                "key,value\n"
                "min_rest_hours,-1\n"
                "max_consecutive_shifts,99\n"
                "weight_pair_avoid_violation,10001"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["errors"] == [
        {
            "field": "value",
            "row_no": 1,
            "code": "INVALID_RANGE",
            "message": "min_rest_hours must be between 0 and 48.",
        },
        {
            "field": "value",
            "row_no": 2,
            "code": "INVALID_RANGE",
            "message": "max_consecutive_shifts must be between 1 and 31.",
        },
        {
            "field": "value",
            "row_no": 3,
            "code": "INVALID_RANGE",
            "message": "weight_pair_avoid_violation must be between 0 and 10000.",
        },
    ]


def test_preview_delimited_import_requires_content(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={"type": "employees", "format": "delimited", "content": ""},
    )

    assert response.status_code == 422


def test_preview_employee_import_uses_current_organization_roles(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "employees",
            "content": (
                "employee_code,name,roles,max_shifts_per_week\n"
                "E003,Park,외부역할,5"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["errors"][0]["code"] == "UNKNOWN_ROLE"


def test_preview_xlsx_employee_import_reports_sheet_row_column_errors(client: TestClient):
    workbook = _xlsx_base64(
        {
            "employees": [
                ["employee_code", "name", "roles", "max_shifts_per_week"],
                ["E003", "", "사수", "5"],
            ]
        }
    )

    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "employees",
            "format": "xlsx",
            "content_base64": workbook,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["errors"] == [
        {
            "sheet": "employees",
            "field": "name",
            "column": "name",
            "row_no": 2,
            "code": "REQUIRED",
            "message": "Required value is missing.",
        }
    ]


def test_preview_xlsx_employee_import_reports_actual_row_after_blank_rows(client: TestClient):
    workbook = _xlsx_base64(
        {
            "employees": [
                ["employee_code", "name", "roles", "max_shifts_per_week"],
                ["", "", "", ""],
                ["E003", "", "사수", "5"],
            ]
        }
    )

    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "employees",
            "format": "xlsx",
            "content_base64": workbook,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["errors"][0]["row_no"] == 3


def test_apply_xlsx_employee_import_blocks_invalid_rows(client: TestClient):
    workbook = _xlsx_base64(
        {
            "employees": [
                ["employee_code", "name", "roles", "max_shifts_per_week"],
                ["E003", "", "사수", "5"],
            ]
        }
    )

    response = client.post(
        "/organizations/org_1/imports/apply",
        json={
            "type": "employees",
            "format": "xlsx",
            "content_base64": workbook,
            "mode": "upsert",
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    employees = client.get("/organizations/org_1/employees").json()
    assert "E003" not in [employee["employee_code"] for employee in employees]


def test_apply_xlsx_shift_type_import_upserts_requirements(client: TestClient):
    workbook = _xlsx_base64(
        {
            "shift_types": [
                [
                    "shift_type",
                    "local_start_time",
                    "local_end_time",
                    "timezone",
                    "crosses_midnight",
                    "active_weekdays",
                    "active",
                    "role_name",
                    "required_count",
                    "unfilled_weight_override",
                ],
                ["야간 근무", "22:00", "06:00", "Asia/Seoul", "true", "0|1|2|3|4", "true", "사수", "1", "500"],
                ["야간 근무", "22:00", "06:00", "Asia/Seoul", "true", "0|1|2|3|4", "true", "부사수", "2", ""],
            ]
        }
    )

    response = client.post(
        "/organizations/org_1/imports/apply",
        json={
            "type": "shift_types",
            "format": "xlsx",
            "content_base64": workbook,
            "mode": "upsert",
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    shift_types = client.get("/organizations/org_1/shift-types").json()
    assert len(shift_types) == 1
    assert shift_types[0]["name"] == "야간 근무"
    assert shift_types[0]["crosses_midnight"] is True
    assert shift_types[0]["active_weekdays"] == [0, 1, 2, 3, 4]
    requirements_by_role = {
        requirement["role_name"]: requirement
        for requirement in shift_types[0]["requirements"]
    }
    assert requirements_by_role["사수"]["required_count"] == 1
    assert requirements_by_role["사수"]["unfilled_weight_override"] == 500
    assert requirements_by_role["부사수"]["required_count"] == 2


def test_preview_shift_type_import_rejects_conflicting_definition(client: TestClient):
    response = client.post(
        "/organizations/org_1/imports/preview",
        json={
            "type": "shift_types",
            "content": (
                "shift_type,local_start_time,local_end_time,timezone,crosses_midnight,active_weekdays,active,role_name,required_count,unfilled_weight_override\n"
                "야간 근무,22:00,06:00,Asia/Seoul,true,0|1|2|3|4,true,사수,1,500\n"
                "야간 근무,23:00,06:00,Asia/Seoul,true,0|1|2|3|4,true,부사수,1,"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["errors"][-1]["code"] == "CONFLICTING_SHIFT_TYPE_DEFINITION"


def _xlsx_base64(sheets: dict[str, list[list[str]]]) -> str:
    workbook = BytesIO()
    with zipfile.ZipFile(workbook, mode="w", compression=zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", _xlsx_content_types(sheets).encode("utf-8"))
        xlsx.writestr("_rels/.rels", _xlsx_root_relationships().encode("utf-8"))
        xlsx.writestr("xl/workbook.xml", _xlsx_workbook_xml(sheets).encode("utf-8"))
        xlsx.writestr(
            "xl/_rels/workbook.xml.rels",
            _xlsx_workbook_relationships(sheets).encode("utf-8"),
        )
        for index, rows in enumerate(sheets.values(), start=1):
            xlsx.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _xlsx_worksheet_xml(rows).encode("utf-8"),
            )
    return base64.b64encode(workbook.getvalue()).decode("ascii")


def _xlsx_worksheet_xml(rows: list[list[str]]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cell_xml = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_xlsx_column_name(column_index)}{row_index}"
            cell_xml.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{html.escape(value)}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cell_xml)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        "</worksheet>"
    )


def _xlsx_content_types(sheets: dict[str, list[list[str]]]) -> str:
    sheet_overrides = "".join(
        (
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        for index in range(1, len(sheets) + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{sheet_overrides}</Types>"
    )


def _xlsx_root_relationships() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _xlsx_workbook_xml(sheets: dict[str, list[list[str]]]) -> str:
    sheet_xml = "".join(
        f'<sheet name="{html.escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheets, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_xml}</sheets>"
        "</workbook>"
    )


def _xlsx_workbook_relationships(sheets: dict[str, list[list[str]]]) -> str:
    relationships = "".join(
        (
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
        for index in range(1, len(sheets) + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{relationships}</Relationships>"
    )


def _xlsx_column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name
