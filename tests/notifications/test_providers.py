from __future__ import annotations

import json
from typing import Any

from work_schedule_ai.notifications.providers import (
    EnvironmentNotificationDeliveryProvider,
    NotificationDelivery,
)


def test_environment_email_provider_sends_smtp_message_from_env_config():
    sent_messages: list[Any] = []
    logins: list[tuple[str, str]] = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self) -> FakeSmtp:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def starttls(self) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            logins.append((username, password))

        def send_message(self, message: Any) -> None:
            sent_messages.append(message)

    provider = EnvironmentNotificationDeliveryProvider.from_env(
        env={
            "WORKSCHEDULEAI_EMAIL_NOTIFICATIONS_ENABLED": "1",
            "WORKSCHEDULEAI_SMTP_HOST": "smtp.example.com",
            "WORKSCHEDULEAI_SMTP_PORT": "2525",
            "WORKSCHEDULEAI_SMTP_USERNAME": "mailer",
            "WORKSCHEDULEAI_SMTP_PASSWORD": "secret",
            "WORKSCHEDULEAI_SMTP_FROM": "noreply@example.com",
            "WORKSCHEDULEAI_NOTIFICATION_EMAIL_TO": "ops@example.com",
        },
        smtp_factory=FakeSmtp,
    )

    assert provider.can_deliver("email") is True
    provider.deliver(_delivery("email"))

    assert logins == [("mailer", "secret")]
    assert len(sent_messages) == 1
    message = sent_messages[0]
    assert message["From"] == "noreply@example.com"
    assert message["To"] == "ops@example.com"
    assert "WorkScheduleAI publication published" in message["Subject"]
    assert "publication_1" in message.get_content()


def test_environment_slack_provider_posts_webhook_payload_from_env_config():
    requests: list[Any] = []

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return b"ok"

    def fake_urlopen(request: Any, timeout: float) -> FakeResponse:
        requests.append((request, timeout))
        return FakeResponse()

    provider = EnvironmentNotificationDeliveryProvider.from_env(
        env={
            "WORKSCHEDULEAI_SLACK_NOTIFICATIONS_ENABLED": "1",
            "WORKSCHEDULEAI_SLACK_WEBHOOK_URL": "https://hooks.slack.example/T000/B000/secret",
        },
        urlopen=fake_urlopen,
    )

    assert provider.can_deliver("slack") is True
    provider.deliver(_delivery("slack"))

    assert len(requests) == 1
    request, timeout = requests[0]
    assert timeout == 10.0
    assert request.full_url == "https://hooks.slack.example/T000/B000/secret"
    body = json.loads(request.data.decode("utf-8"))
    assert "publication_1" in body["text"]
    assert "secret" not in body["text"]


def _delivery(channel: str) -> NotificationDelivery:
    return NotificationDelivery(
        notification_id="notification_1",
        organization_id="org_1",
        publication_id="publication_1",
        employee_id="emp_1",
        notification_type="published",
        channel=channel,
        subject="WorkScheduleAI publication published",
        body="Publication publication_1 was published for employee emp_1.",
    )
