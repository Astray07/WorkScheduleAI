from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import EmailMessage
import json
import os
import smtplib
from typing import Any, Protocol
from urllib import request as url_request


@dataclass(frozen=True)
class NotificationDelivery:
    notification_id: str
    organization_id: str
    publication_id: str
    employee_id: str
    notification_type: str
    channel: str
    subject: str
    body: str
    recipient: str | None = None


class NotificationDeliveryProvider(Protocol):
    def can_deliver(self, channel: str) -> bool:
        ...

    def deliver(self, delivery: NotificationDelivery) -> None:
        ...


@dataclass(frozen=True)
class _EmailConfig:
    enabled: bool
    smtp_host: str
    smtp_port: int
    sender: str
    recipient_override: str
    username: str | None
    password: str | None
    use_tls: bool
    timeout_seconds: float


@dataclass(frozen=True)
class _SlackConfig:
    enabled: bool
    webhook_url: str
    timeout_seconds: float


class EnvironmentNotificationDeliveryProvider:
    def __init__(
        self,
        *,
        email_config: _EmailConfig,
        slack_config: _SlackConfig,
        smtp_factory: Callable[..., Any] = smtplib.SMTP,
        urlopen: Callable[..., Any] = url_request.urlopen,
    ) -> None:
        self._email_config = email_config
        self._slack_config = slack_config
        self._smtp_factory = smtp_factory
        self._urlopen = urlopen

    @classmethod
    def from_env(
        cls,
        *,
        env: Mapping[str, str] | None = None,
        smtp_factory: Callable[..., Any] = smtplib.SMTP,
        urlopen: Callable[..., Any] = url_request.urlopen,
    ) -> EnvironmentNotificationDeliveryProvider:
        source = env if env is not None else os.environ
        return cls(
            email_config=_EmailConfig(
                enabled=_env_flag(source, "WORKSCHEDULEAI_EMAIL_NOTIFICATIONS_ENABLED"),
                smtp_host=source.get("WORKSCHEDULEAI_SMTP_HOST", ""),
                smtp_port=_env_int(source, "WORKSCHEDULEAI_SMTP_PORT", 587),
                sender=source.get("WORKSCHEDULEAI_SMTP_FROM", ""),
                recipient_override=source.get(
                    "WORKSCHEDULEAI_NOTIFICATION_EMAIL_TO",
                    "",
                ),
                username=source.get("WORKSCHEDULEAI_SMTP_USERNAME") or None,
                password=source.get("WORKSCHEDULEAI_SMTP_PASSWORD") or None,
                use_tls=_env_flag(source, "WORKSCHEDULEAI_SMTP_TLS", default=True),
                timeout_seconds=_env_float(
                    source,
                    "WORKSCHEDULEAI_NOTIFICATION_TIMEOUT_SECONDS",
                    10.0,
                ),
            ),
            slack_config=_SlackConfig(
                enabled=_env_flag(source, "WORKSCHEDULEAI_SLACK_NOTIFICATIONS_ENABLED"),
                webhook_url=source.get("WORKSCHEDULEAI_SLACK_WEBHOOK_URL", ""),
                timeout_seconds=_env_float(
                    source,
                    "WORKSCHEDULEAI_NOTIFICATION_TIMEOUT_SECONDS",
                    10.0,
                ),
            ),
            smtp_factory=smtp_factory,
            urlopen=urlopen,
        )

    def can_deliver(self, channel: str) -> bool:
        if channel == "email":
            return (
                self._email_config.enabled
                and bool(self._email_config.smtp_host)
                and bool(self._email_config.sender)
            )
        if channel == "slack":
            return (
                self._slack_config.enabled
                and bool(self._slack_config.webhook_url)
            )
        return False

    def deliver(self, delivery: NotificationDelivery) -> None:
        if delivery.channel == "email":
            self._deliver_email(delivery)
            return
        if delivery.channel == "slack":
            self._deliver_slack(delivery)
            return
        raise ValueError(f"Unsupported notification channel: {delivery.channel}")

    def _deliver_email(self, delivery: NotificationDelivery) -> None:
        if not self.can_deliver("email"):
            raise ValueError("Email notification provider is not configured")
        recipient = delivery.recipient or self._email_config.recipient_override
        if not recipient:
            raise ValueError("Email notification recipient is not configured")
        message = EmailMessage()
        message["From"] = self._email_config.sender
        message["To"] = recipient
        message["Subject"] = delivery.subject
        message.set_content(delivery.body)
        with self._smtp_factory(
            self._email_config.smtp_host,
            self._email_config.smtp_port,
            timeout=self._email_config.timeout_seconds,
        ) as smtp:
            if self._email_config.use_tls:
                smtp.starttls()
            if self._email_config.username and self._email_config.password:
                smtp.login(
                    self._email_config.username,
                    self._email_config.password,
                )
            smtp.send_message(message)

    def _deliver_slack(self, delivery: NotificationDelivery) -> None:
        if not self.can_deliver("slack"):
            raise ValueError("Slack notification provider is not configured")
        payload = json.dumps({"text": delivery.body}).encode("utf-8")
        request = url_request.Request(
            self._slack_config.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._urlopen(request, timeout=self._slack_config.timeout_seconds) as response:
            response.read()


def _env_flag(
    env: Mapping[str, str],
    name: str,
    *,
    default: bool = False,
) -> bool:
    value = env.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(env.get(name, str(default)))
    except ValueError:
        return default


def _env_float(env: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(env.get(name, str(default)))
    except ValueError:
        return default
