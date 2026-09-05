"""Email verification code generation, hashing, and delivery.

Codes are 6 numeric digits (configurable), stored only as a SHA-256 hash
so a database leak can't be replayed. Delivery is pluggable via the
``EMAIL_BACKEND`` setting:

- ``log``  (default, dev/demo) — prints the code to the server console.
- ``smtp`` (production) — sends a real email via SMTP.

In ``log`` mode the code is also recorded in ``verification.last_sent``
keyed by email so integration tests can read it back without hitting a
real mail server. This is *not* exposed through any API route — it only
exists in the service's in-memory state.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from secrets import randbelow

from ..config import Settings

_log = logging.getLogger("unilead.verification")

_settings = Settings()

# email → code, set only when EMAIL_BACKEND=log (dev/tests).
last_sent: dict[str, str] = {}


def _utcnow() -> datetime:
    """Timezone-naive UTC now — matches SQLite datetime storage."""
    return datetime.now(UTC).replace(tzinfo=None)


def code_ttl_seconds() -> int:
    return _settings.verification_code_ttl_minutes * 60


def generate_code() -> str:
    """Return a random numeric code (leading zeros preserved)."""
    code = str(randbelow(10 ** _settings.verification_code_length))
    return code.zfill(_settings.verification_code_length)


def hash_code(code: str) -> str:
    """SHA-256 hash of a code. Codes are short — a hash is stored in the DB."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_code(provided: str, stored_hash: str | None) -> bool:
    """Constant-time comparison of a submitted code against the stored hash."""
    if not stored_hash:
        return False
    return hmac.compare_digest(hash_code(provided), stored_hash)


def _send_via_log(email: str, code: str) -> None:
    last_sent[email] = code
    _log.info(
        "EMAIL VERIFICATION CODE for %s: %s (expires in %d min)",
        email,
        code,
        _settings.verification_code_ttl_minutes,
    )


def _send_via_smtp(email: str, code: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Unilead verification code"
    msg["From"] = _settings.smtp_from_email
    msg["To"] = email
    text = (
        f"Your Unilead verification code is {code}.\n\n"
        f"It expires in {_settings.verification_code_ttl_minutes} minutes.\n"
        "If you didn't create an account, you can ignore this email.\n"
    )
    html = (
        "<html><body><p>Your Unilead verification code is</p>"
        f"<p style='font-size:28px;letter-spacing:6px;font-weight:bold'>{code}</p>"
        f"<p>It expires in {_settings.verification_code_ttl_minutes} minutes.</p>"
        "<p>If you didn't create an account, you can ignore this email.</p>"
        "</body></html>"
    )
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(_settings.smtp_host, _settings.smtp_port, timeout=15) as server:
        if _settings.smtp_starttls:
            server.starttls()
        if _settings.smtp_username:
            server.login(_settings.smtp_username, _settings.smtp_password)
        server.sendmail(_settings.smtp_from_email, [email], msg.as_string())


def send_code(email: str, code: str) -> None:
    """Deliver a verification code to ``email`` per the configured backend."""
    if _settings.email_backend == "smtp":
        _send_via_smtp(email, code)
    else:
        _send_via_log(email, code)


def cooldown_remaining(sent_at: datetime | None) -> float:
    """Seconds left until the resend cooldown clears (0 if None/passed).

    ``sent_at`` is the naive-UTC ``email_verification_sent_at`` value.
    """
    if sent_at is None:
        return 0.0
    now = _utcnow()
    elapsed = (now - sent_at).total_seconds()
    remain = _settings.verification_resend_cooldown_seconds - elapsed
    return max(0.0, remain)
