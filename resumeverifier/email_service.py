"""Email service: sends verification emails via Maileroo SMTP.

Env vars: SMTP_USERNAME, SMTP_PASSWORD, SMTP_HOST, SMTP_PORT, FROM_EMAIL, API_BASE_URL
Returns False silently when SMTP_USERNAME is not set (allows tests to run without credentials).
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_MAILEROO_HOST = os.environ.get("SMTP_HOST", "smtp.maileroo.com")
_MAILEROO_PORT = int(os.environ.get("SMTP_PORT", "587"))
_MAILEROO_USERNAME = os.environ.get("SMTP_USERNAME", "")
_MAILEROO_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
_FROM_EMAIL = os.environ.get("FROM_EMAIL", _MAILEROO_USERNAME or "noreply@resumeverifier.com")
_API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:5000")


def send_verification_email(
    verifier_email, verifier_name, position_title,
    company_name, requester_name, verification_token,
):
    """Send a verification request email; returns True on success, False otherwise."""
    if not _MAILEROO_USERNAME:
        logger.warning("SMTP_USERNAME not set; skipping email send.")
        return False

    verify_url = f"{_API_BASE_URL}/api/verify/{verification_token}?action=verified"
    reject_url = f"{_API_BASE_URL}/api/verify/{verification_token}?action=rejected"

    body = (
        f"Dear {verifier_name},\n\n"
        f"{requester_name} has requested that you verify their role as "
        f"{position_title} at {company_name}.\n\n"
        f"CONFIRM (click to verify):\n{verify_url}\n\n"
        f"REJECT (click to reject):\n{reject_url}\n\n"
        f"These links will expire in 30 days.\n\n"
        f"Best regards,\nResume Verifier"
    )

    msg = MIMEMultipart()
    msg["From"] = _FROM_EMAIL
    msg["To"] = verifier_email
    msg["Subject"] = (
        f"Verification Request from {requester_name}: {position_title} at {company_name}"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(_MAILEROO_HOST, _MAILEROO_PORT) as server:
            server.starttls()
            server.login(_MAILEROO_USERNAME, _MAILEROO_PASSWORD)
            server.send_message(msg)
        logger.info("Verification email sent to %s", verifier_email)
        return True
    except smtplib.SMTPException as exc:
        logger.error("Failed to send verification email: %s", exc)
        return False
