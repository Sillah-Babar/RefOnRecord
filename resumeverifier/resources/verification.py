"""Verification endpoints: GET/POST /api/experiences/<experience>/verification-requests/,
GET /api/verification-requests/<vr>/, POST /api/verification-requests/<id>/respond/,
GET /api/verify/<token>?action=verified|rejected"""
from datetime import datetime

from flask import g, request, jsonify, make_response
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker

from resumeverifier import db
from resumeverifier.auth import require_auth
from resumeverifier.constants import (
    VERIFICATION_CREATE_SCHEMA,
    VERIFICATION_RESPOND_SCHEMA,
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    error_response,
)
from resumeverifier.models import Experience, VerificationRequest
from resumeverifier.resources import api_blueprint


class ExperienceVerificationCollection(MethodView):
    """List and create verification requests for an experience."""

    decorators = [require_auth]

    def get(self, experience):
        """List all verification requests."""
        if g.current_user.user_id != experience.project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        requests = [vr.serialize() for vr in experience.verification_requests]
        return jsonify(requests), HTTP_200_OK

    def post(self, experience):
        """Create a verification request and send email."""
        if g.current_user.user_id != experience.project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        data = request.get_json(silent=True)
        if data is None:
            return error_response("Request body must be JSON", HTTP_400_BAD_REQUEST)

        try:
            validate(
                data, VERIFICATION_CREATE_SCHEMA, format_checker=FormatChecker()
            )
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        vr = VerificationRequest(
            experience_id=experience.experience_id,
            verifier_name=data["verifier_name"],
            verifier_position=data["verifier_position"],
            verifier_email=data["verifier_email"],
            verification_token=VerificationRequest.generate_token(),
        )
        experience.verification_status = "pending"
        db.session.add(vr)
        db.session.commit()

        from resumeverifier.email_service import send_verification_email  # pylint: disable=import-outside-toplevel
        send_verification_email(
            verifier_email=data["verifier_email"],
            verifier_name=data["verifier_name"],
            position_title=experience.position_title,
            company_name=experience.company_name,
            requester_name=g.current_user.username,
            verification_token=vr.verification_token,
        )

        response = jsonify(vr.serialize())
        response.status_code = HTTP_201_CREATED
        response.headers["Location"] = (
            f"/api/verification-requests/{vr.request_id}/"
        )
        return response


class VerificationRequestResource(MethodView):
    """Get a single verification request (owner only)."""

    decorators = [require_auth]

    def get(self, vr):
        """Get verification request."""
        if g.current_user.user_id != vr.experience.project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        return jsonify(vr.serialize()), HTTP_200_OK


class VerificationRespondResource(MethodView):
    """Verifier responds with token from email (no bearer auth needed)."""

    def post(self, request_id):
        """Submit verified/rejected decision using email token."""
        vr = db.session.get(VerificationRequest, request_id)
        if vr is None:
            return error_response(
                f"Verification request {request_id} not found", HTTP_404_NOT_FOUND
            )

        data = request.get_json(silent=True)
        if data is None:
            return error_response("Request body must be JSON", HTTP_400_BAD_REQUEST)

        try:
            validate(
                data, VERIFICATION_RESPOND_SCHEMA, format_checker=FormatChecker()
            )
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        if data["verification_token"] != vr.verification_token:
            return error_response("Invalid verification token", HTTP_400_BAD_REQUEST)

        if vr.expires_at < datetime.utcnow():
            return error_response(
                "Verification token has expired", HTTP_400_BAD_REQUEST
            )

        if vr.status != "pending":
            return error_response(
                f"Request already has status '{vr.status}'", HTTP_400_BAD_REQUEST
            )

        vr.status = data["status"]
        vr.verifier_comment = data.get("verifier_comment")
        vr.responded_at = datetime.utcnow()

        experience = db.session.get(Experience, vr.experience_id)
        experience.verification_status = data["status"]

        db.session.commit()
        return jsonify(vr.serialize()), HTTP_200_OK


@api_blueprint.route("/verify/<string:token>", methods=["GET"])
def verify_by_token(token):
    """Handle email verify/reject link click; returns HTML page."""
    vr = VerificationRequest.query.filter_by(verification_token=token).first()
    if vr is None:
        return error_response("Verification token not found", HTTP_404_NOT_FOUND)

    if vr.expires_at < datetime.utcnow():
        return error_response("Verification token has expired", HTTP_400_BAD_REQUEST)

    if vr.status != "pending":
        return error_response(
            f"Request already has status '{vr.status}'", HTTP_400_BAD_REQUEST
        )

    action = request.args.get("action", "verified")
    if action not in ("verified", "rejected"):
        return error_response(
            "action must be 'verified' or 'rejected'", HTTP_400_BAD_REQUEST
        )

    vr.status = action
    vr.responded_at = datetime.utcnow()

    experience = db.session.get(Experience, vr.experience_id)
    experience.verification_status = action

    db.session.commit()

    if action == "verified":
        color, icon, heading, message = "#22c55e", "✅", "Verification Confirmed", (
            f"You have successfully verified that <strong>{experience.project.owner.username}</strong> "
            f"worked as <strong>{experience.position_title}</strong> "
            f"at <strong>{experience.company_name}</strong>."
        )
    else:
        color, icon, heading, message = "#ef4444", "❌", "Verification Rejected", (
            f"You have rejected the verification request for "
            f"<strong>{experience.position_title}</strong> "
            f"at <strong>{experience.company_name}</strong>."
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{heading} – RefOnRecord</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f9fafb; display: flex; align-items: center;
           justify-content: center; min-height: 100vh; margin: 0; }}
    .card {{ background: #fff; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,.08);
             padding: 48px 40px; max-width: 480px; width: 90%; text-align: center; }}
    .icon {{ font-size: 64px; margin-bottom: 16px; }}
    h1 {{ color: {color}; margin: 0 0 12px; font-size: 1.6rem; }}
    p {{ color: #6b7280; line-height: 1.6; margin: 0; }}
    strong {{ color: #111827; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h1>{heading}</h1>
    <p>{message}</p>
  </div>
</body>
</html>"""

    return make_response(html, HTTP_200_OK)


api_blueprint.add_url_rule(
    "/experiences/<experience:experience>/verification-requests/",
    view_func=ExperienceVerificationCollection.as_view(
        "experience_verification_collection"
    ),
    methods=["GET", "POST"],
)
api_blueprint.add_url_rule(
    "/verification-requests/<vr:vr>/",
    view_func=VerificationRequestResource.as_view("verification_request_resource"),
    methods=["GET"],
)
api_blueprint.add_url_rule(
    "/verification-requests/<int:request_id>/respond/",
    view_func=VerificationRespondResource.as_view("verification_respond"),
    methods=["POST"],
)
