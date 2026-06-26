from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from work_schedule_ai.db.models import (
    EmployeeUserLink,
    PublicationNotification,
    User,
    utc_now,
)
from work_schedule_ai.notifications.providers import (
    EnvironmentNotificationDeliveryProvider,
    NotificationDelivery,
    NotificationDeliveryProvider,
)


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
    provider: NotificationDeliveryProvider | None = None,
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
    delivery_provider = provider or EnvironmentNotificationDeliveryProvider.from_env()
    for notification in notifications:
        notification.delivery_attempts += 1
        if notification.channel == "in_app":
            notification.status = "sent"
            notification.delivered_at = utc_now()
            notification.last_delivery_error = None
            sent += 1
        elif delivery_provider.can_deliver(notification.channel):
            try:
                delivery_provider.deliver(
                    _delivery_from_notification(db_session, notification)
                )
            except Exception as exc:
                notification.status = "failed"
                notification.delivered_at = None
                notification.last_delivery_error = (
                    f"delivery_failed:{notification.channel}:{type(exc).__name__}"
                )
                failed += 1
            else:
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


def _delivery_from_notification(
    db_session: Session,
    notification: PublicationNotification,
) -> NotificationDelivery:
    subject = f"WorkScheduleAI publication {notification.notification_type}"
    body = "\n".join(
        [
            f"Publication {notification.publication_id} was {notification.notification_type}.",
            f"Organization: {notification.organization_id}",
            f"Employee: {notification.employee_id}",
            f"Notification: {notification.id}",
        ]
    )
    return NotificationDelivery(
        notification_id=notification.id,
        organization_id=notification.organization_id,
        publication_id=notification.publication_id,
        employee_id=notification.employee_id,
        notification_type=notification.notification_type,
        channel=notification.channel,
        subject=subject,
        body=body,
        recipient=_recipient_for_notification(db_session, notification),
    )


def _recipient_for_notification(
    db_session: Session,
    notification: PublicationNotification,
) -> str | None:
    if notification.channel != "email":
        return None
    return db_session.execute(
        select(User.email)
        .join(EmployeeUserLink, EmployeeUserLink.user_id == User.id)
        .where(
            EmployeeUserLink.organization_id == notification.organization_id,
            EmployeeUserLink.employee_id == notification.employee_id,
            EmployeeUserLink.status == "linked",
        )
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(1)
    ).scalar_one_or_none()
