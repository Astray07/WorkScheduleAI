from __future__ import annotations

from collections.abc import Generator
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from work_schedule_ai.db.models import (
    Base,
    Employee,
    Organization,
    PublicationNotification,
    SchedulePublication,
    ScheduleRun,
)
from work_schedule_ai.notifications.dispatcher import dispatch_pending_notifications


def test_dispatcher_marks_in_app_notifications_sent_without_external_provider():
    session = _session()
    notification = session.get(PublicationNotification, "notification_in_app")
    assert notification is not None

    summary = dispatch_pending_notifications(session)

    assert summary.sent == 1
    assert summary.suppressed == 1
    assert summary.failed == 0
    session.refresh(notification)
    assert notification.status == "sent"
    assert notification.delivered_at is not None
    assert notification.delivery_attempts == 1
    assert notification.last_delivery_error is None
    email_notification = session.get(PublicationNotification, "notification_email")
    assert email_notification is not None
    assert email_notification.status == "suppressed"
    assert email_notification.delivered_at is None
    assert email_notification.delivery_attempts == 1
    assert "provider_not_configured" in (email_notification.last_delivery_error or "")


def test_dispatcher_does_not_log_or_store_signed_link_tokens():
    session = _session()

    dispatch_pending_notifications(session)

    notifications = session.query(PublicationNotification).all()
    serialized = "\n".join(
        f"{notification.status} {notification.last_delivery_error or ''}"
        for notification in notifications
    )
    assert "token" not in serialized.lower()
    assert "employee-link" not in serialized.lower()


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all(_rows())
    session.commit()
    return session


def _rows() -> Generator[object, None, None]:
    yield Organization(id="org_1", name="Clinic A", timezone="Asia/Seoul")
    yield Employee(id="emp_1", organization_id="org_1", employee_code="E001", name="Kim")
    yield ScheduleRun(
        id="run_1",
        organization_id="org_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        template="one_shift_per_day",
        deterministic_mode=True,
        timeout_seconds=30,
        status="succeeded",
        solver_status="cp_sat_optimal",
        solution_quality="optimal",
        current_attempt_no=1,
        recalculation_count=0,
    )
    yield SchedulePublication(
        id="publication_1",
        organization_id="org_1",
        schedule_run_id="run_1",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 7),
        status="published",
        assignment_snapshot_hash="assignment_hash",
        issue_snapshot_hash="issue_hash",
    )
    yield PublicationNotification(
        id="notification_in_app",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        notification_type="published",
        channel="in_app",
        status="pending_recorded",
    )
    yield PublicationNotification(
        id="notification_email",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        notification_type="published",
        channel="email",
        status="pending_recorded",
    )
