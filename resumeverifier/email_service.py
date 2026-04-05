"""Email service: sends verification emails via Maileroo HTTP API.

Env vars: SENDING_API_KEY, FROM_EMAIL, API_BASE_URL
Returns False silently when SENDING_API_KEY is not set (allows tests to run without credentials).
"""
import logging
import os

import requests as http

logger = logging.getLogger(__name__)

_MAILEROO_SEND_URL = "https://smtp.maileroo.com/send"
_SENDING_API_KEY = os.environ.get("SENDING_API_KEY", "")
_FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@46871dc7c50f7650.maileroo.org")
_API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:5000")


def send_verification_email(
    verifier_email, verifier_name, position_title,
    company_name, requester_name, verification_token,
):
    """Send a verification request email via Maileroo HTTP API.

    Returns True on success, False otherwise.
    """
    if not _SENDING_API_KEY:
        logger.warning("SENDING_API_KEY not set; skipping email send.")
        return False

    verify_url = f"{_API_BASE_URL}/api/verify/{verification_token}?action=verified"
    reject_url = f"{_API_BASE_URL}/api/verify/{verification_token}?action=rejected"

    plain = (
        f"Dear {verifier_name},\n\n"
        f"{requester_name} has requested that you verify their role as "
        f"{position_title} at {company_name}.\n\n"
        f"CONFIRM:\n{verify_url}\n\n"
        f"REJECT:\n{reject_url}\n\n"
        f"These links expire in 30 days.\n\n"
        f"Best regards,\nRefOnRecord"
    )
    html = f"""
<p>Dear {verifier_name},</p>
<p><strong>{requester_name}</strong> has requested that you verify their role as
<strong>{position_title}</strong> at <strong>{company_name}</strong>.</p>
<p>
  <a href="{verify_url}" style="color:#22c55e;font-weight:bold;">Verify experience</a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="{reject_url}" style="color:#ef4444;font-weight:bold;">Reject request</a>
</p>
<p><em>These links expire in 30 days.</em></p>
<p>Best regards,<br>RefOnRecord</p>
"""

    payload = {
        "from": _FROM_EMAIL,
        "to": verifier_email,
        "subject": f"Verification Request from {requester_name}: {position_title} at {company_name}",
        "plain": plain,
        "html": html,
    }
    headers = {"X-API-Key": _SENDING_API_KEY}

    try:
        resp = http.post(_MAILEROO_SEND_URL, data=payload, headers=headers, timeout=15)
        if resp.ok:
            logger.info("Verification email sent to %s", verifier_email)
            return True
        logger.error("Maileroo API error: %s %s", resp.status_code, resp.text)
        return False
    except http.exceptions.RequestException as exc:
        logger.error("Failed to send verification email: %s", exc)
        return False
