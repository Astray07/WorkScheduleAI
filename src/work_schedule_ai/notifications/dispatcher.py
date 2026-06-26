from __future__ import annotations

from dataclasses import dataclass
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.db.models import PublicationNotification, utc_now


PENDING_STATUS = "pending_recorded"


@dataclass(frozen=True)
class NotificationDispatchSummary:
    sent: int
    suppressed: int
    failed: int


def dispatch_pending_notifications(
    db_session: Session,
    *,
    organization_id: str | None = None,
    limit: int = 100,
) -> NotificationDispatchSummary:
    query = select(PublicationNotification).where(
        PublicationNotification.status == PENDING_STATUS
    )
    if organization_id is not None:
        query = query.where(PublicationNotification.organization_id == organization_id)
    query = query.order_by(
        PublicationNotification.created_at, PublicationNotification.id
    ).limit(limit)
    notifications = list(
        db_session.execute(query).scalars()
    )
    sent = 0
    suppressed = 0
    failed = 0
    for notification in notifications:
        notification.delivery_attempts += 1
        if _can_deliver(notification.channel):
            notification.status = "sent"
            notification.delivered_at = utc_now()
            notification.last_delivery_error = None
            sent += 1
        else:
            notification.status = "suppressed"
            notification.delivered_at = None
            notification.last_delivery_error = (
                f"provider_not_configured:{notification.channel}"
            )
            suppressed += 1
    db_session.commit()
    return NotificationDispatchSummary(sent=sent, suppressed=suppressed, failed=failed)


def _can_deliver(channel: str) -> bool:
    if channel == "in_app":
        return True
    if channel == "email":
        return os.environ.get("WORKSCHEDULEAI_EMAIL_NOTIFICATIONS_ENABLED") == "1"
    if channel == "slack":
        return os.environ.get("WORKSCHEDULEAI_SLACK_NOTIFICATIONS_ENABLED") == "1"
    return False
