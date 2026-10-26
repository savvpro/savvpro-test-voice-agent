"""SMTP verification and private appointment notifications."""
from __future__ import annotations

import re
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from secrets import randbelow

from . import config as C
from .db import Database


def _format_time(minutes: int) -> str:
    hour, minute = divmod(minutes, 60)
    return f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"


class EmailService:
    def __init__(self, db: Database, smtp_factory=None):
        self.db = db
        self.smtp_factory = smtp_factory or smtplib.SMTP

    @staticmethod
    def _safe_text(value: object) -> str:
        return re.sub(r"[\r\n\x00-\x1f\x7f]", " ", str(value)).strip()

    def _send(self, recipient: str, subject: str, body: str) -> bool:
        if not self.db.valid_email(recipient) or not self.db.valid_email(C.SMTP_SENDER):
            return False
        if not C.SMTP_HOST:
            return False
        message = EmailMessage()
        message["From"] = C.SMTP_SENDER
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        try:
            context = ssl.create_default_context()
            if C.SMTP_USE_TLS:
                with self.smtp_factory(C.SMTP_HOST, C.SMTP_PORT, timeout=15) as smtp:
                    smtp.starttls(context=context)
                    if C.SMTP_USERNAME:
                        smtp.login(C.SMTP_USERNAME, C.SMTP_PASSWORD)
                    refused = smtp.send_message(message)
            else:
                with smtplib.SMTP_SSL(C.SMTP_HOST, C.SMTP_PORT, timeout=15, context=context) as smtp:
                    if C.SMTP_USERNAME:
                        smtp.login(C.SMTP_USERNAME, C.SMTP_PASSWORD)
                    refused = smtp.send_message(message)
            return not refused
        except (OSError, smtplib.SMTPException, ssl.SSLError, ValueError):
            return False

    def send_verification(self, session_id: str, email: str, purpose: str) -> bool:
        if not self.db.valid_email(email):
            return False
        code = f"{randbelow(1_000_000):06d}"
        self.db.create_email_challenge(session_id, email, purpose, code)
        body = (
            "A request was made to verify this email address for the Children's Specialist Clinic.\n"
            f"Your one-time verification code is {code}.\n"
            "It expires in 10 minutes. If you did not request this code, you can ignore this message.\n"
            "This email does not confirm or identify any appointment."
        )
        return self._send(email, "Clinic email verification", body)

    def verify_code(self, session_id: str, email: str, purpose: str, code: str) -> bool:
        return self.db.verify_email_challenge(session_id, email, purpose, code)

    def send_pending_notifications(self, limit: int = 20) -> tuple[int, int]:
        sent = failed = 0
        for notification in self.db.claim_notifications(limit):
            parsed_date = date.fromisoformat(notification["appointment_date"])
            event_text = {
                "booked": "Booking confirmed",
                "cancelled": "Appointment cancelled",
                "rescheduled": "Appointment rescheduled",
            }[notification["event"]]
            body = (
                f"{event_text}\n\n"
                f"Child: {self._safe_text(notification['child_name'])}\n"
                f"Parent or guardian: {self._safe_text(notification['guardian_name'])}\n"
                f"Token number: {notification['token']}\n"
                f"Date: {parsed_date.strftime('%A, %B')} {parsed_date.day}, {parsed_date.year}\n"
                f"Time: {_format_time(notification['start_min'])}\n"
                f"Status: {self._safe_text(notification['status'])}\n\n"
                "This confidential appointment notice was sent to the verified email address on file."
            )
            delivered = self._send(notification["email"], "Clinic appointment update", body)
            self.db.finish_notification(notification["notification_id"], delivered)
            sent += int(delivered)
            failed += int(not delivered)
        return sent, failed