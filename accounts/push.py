"""Optional Telegram / email push for schedule updates (env-configured)."""

from __future__ import annotations

import logging
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def telegram_send_message(text: str) -> bool:
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
    chat_id = (getattr(settings, "TELEGRAM_CHAT_ID", None) or "").strip()
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:4000]}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False


def email_send(subject: str, body: str, to_email: str) -> bool:
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
        return True
    except Exception as exc:
        logger.warning("Email send failed: %s", exc)
        return False


def push_schedule_change_broadcast(
    *,
    organization_id: int,
    headline: str,
    detail: str = "",
    in_app_reason: str = "",
) -> dict[str, Any]:
    """
    Telegram (if configured) + optional email to MATIKA_SCHEDULE_NOTIFY_EMAIL.
    Returns small stats dict for logging.
    """
    from accounts.models import User

    text = headline if not detail else f"{headline}\n{detail}"
    tg_ok = telegram_send_message(text)
    notify_addr = (getattr(settings, "SCHEDULE_NOTIFY_EMAIL", None) or "").strip()
    mail_ok = False
    if notify_addr:
        mail_ok = email_send("MATIKA: " + headline[:120], text, notify_addr)

    n_inapp = 0
    try:
        from accounts.notification_kinds import SCHEDULE_UPDATED
        from accounts.notifications import notify_user

        payload = {"headline": headline, "detail": detail}
        if in_app_reason:
            payload["reason"] = in_app_reason
        for u in User.objects.filter(organization_id=organization_id).exclude(role=User.Role.ADMIN):
            notify_user(
                user=u,
                kind=SCHEDULE_UPDATED,
                payload=payload,
            )
            n_inapp += 1
    except Exception as exc:
        logger.warning("In-app schedule notifications failed: %s", exc)

    return {"telegram": tg_ok, "email": mail_ok, "in_app": n_inapp}
