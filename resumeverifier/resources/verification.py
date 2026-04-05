"""
Verification request endpoints:
- GET/POST /api/users/<user>/projects/<project>/experiences/<experience>/verification-requests/
  — list and create verification requests for a work experience
- GET /api/users/<user>/projects/<project>/experiences/<experience>/verification-requests/<vr>/
  — retrieve a single verification request (owner only)
- POST /api/verification-requests/<id>/respond/
  — verifier submits their decision using the token from the email (M2M API key required)
- GET /api/verify/<token>?action=verified|rejected
  — email link handler; sets status and returns an HTML confirmation page
"""
from datetime import datetime

from flask import g, request, jsonify, make_response, url_for
from flask.views import MethodView
from jsonschema import validate, ValidationError, FormatChecker

from resumeverifier.extensions import db
from resumeverifier.auth import require_auth, require_m2m_auth
from resumeverifier.constants import (
    VERIFICATION_CREATE_SCHEMA,
    VERIFICATION_RESPOND_SCHEMA,
    VERIFICATION_EXPIRE_SCHEMA,
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
    """
    List and create verification requests for a work experience.

    GET returns all requests for the experience (owner only).
    POST creates a new request and sends a verification email to the verifier.
    """

    decorators = [require_auth]

    def get(self, user, project, experience):
        """
        List all verification requests for the given experience.

        Requires the authenticated user to own the parent project.
        """
        if g.current_user.user_id != experience.project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        requests = [vr.serialize() for vr in experience.verification_requests]
        return jsonify(requests), HTTP_200_OK

    def post(self, user, project, experience):
        """
        Create a new verification request and dispatch the verifier email.

        Validates body against VERIFICATION_CREATE_SCHEMA.
        Sets the experience verification_status to 'pending'.
        Sends an email to the verifier via ``send_verification_email``.
        Returns 201 with a Location header pointing to the new resource.
        """
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
        response.headers["Location"] = url_for(
            "api.verification_request_resource",
            user=experience.project.owner,
            project=experience.project,
            experience=experience,
            vr=vr,
        )
        return response


class VerificationRequestResource(MethodView):
    """
    Retrieve a single verification request.

    Access is restricted to the owner of the parent experience/project.
    """

    decorators = [require_auth]

    def get(self, user, project, experience, vr):
        """
        Get a verification request by its ID.

        Returns 403 if the requester does not own the parent project.
        """
        if g.current_user.user_id != vr.experience.project.user_id:
            return error_response("Forbidden", HTTP_403_FORBIDDEN)

        return jsonify(vr.serialize()), HTTP_200_OK


class VerificationRespondResource(MethodView):
    """
    Allow a verifier to submit their decision for a verification request.

    Protected by Machine-to-Machine API key authentication (X-API-Key header).
    The verifier proves their identity using the token from the email.
    """

    decorators = [require_m2m_auth]

    def post(self, request_id):
        """
        Submit a verified or rejected decision for a verification request.

        Validates the verification_token against the stored token.
        Checks the request is still pending and not expired.
        Updates both the VerificationRequest status and the parent Experience
        verification_status to match the decision.
        Returns the updated VerificationRequest JSON on success.
        """
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


class VerificationRequestM2MCollection(MethodView):
    """
    M2M: list verification requests across all users with optional filters.

    Intended for automated services (e.g. reminder service) that need to
    query pending or expired requests without a user session.

    Query parameters:
    - status: filter by status (pending, verified, rejected, expired)
    - older_than: only return requests older than N days
    - expired: if 'true', only return requests whose token has expired
    """

    decorators = [require_m2m_auth]

    def get(self):
        """
        List verification requests with optional query-string filters.

        Returns each request serialised with embedded experience and project
        context so the caller avoids extra round-trips.
        """
        status = request.args.get("status")
        older_than = request.args.get("older_than", type=int)
        expired = request.args.get("expired", "").lower() == "true"

        query = VerificationRequest.query
        if status:
            query = query.filter(VerificationRequest.status == status)
        if older_than is not None:
            from datetime import timedelta  # pylint: disable=import-outside-toplevel
            cutoff = datetime.utcnow() - timedelta(days=older_than)
            query = query.filter(VerificationRequest.requested_at < cutoff)
        if expired:
            query = query.filter(VerificationRequest.expires_at < datetime.utcnow())

        return jsonify([_serialize_vr_full(vr) for vr in query.all()]), HTTP_200_OK


class VerificationRequestM2MResource(MethodView):
    """
    M2M: retrieve or expire a single verification request by its ID.

    GET returns full context (verifier details, experience, project owner).
    PATCH allows the reminder service to mark a token as expired
    (only allowed when status is still pending).
    """

    decorators = [require_m2m_auth]

    def get(self, request_id):
        """
        Retrieve a single verification request with full context.

        Returns verifier details, experience info, and project owner name
        so the caller can compose a reminder email without extra API calls.
        """
        vr = db.session.get(VerificationRequest, request_id)
        if vr is None:
            return error_response(
                f"Verification request {request_id} not found", HTTP_404_NOT_FOUND
            )
        return jsonify(_serialize_vr_full(vr)), HTTP_200_OK

    def patch(self, request_id):
        """
        Mark a pending verification request as expired.

        Only accepts ``{"status": "expired"}``.
        Resets the parent experience's verification_status to 'not_requested'
        so the resume owner can send a fresh request.
        """
        vr = db.session.get(VerificationRequest, request_id)
        if vr is None:
            return error_response(
                f"Verification request {request_id} not found", HTTP_404_NOT_FOUND
            )

        data = request.get_json(silent=True)
        if data is None:
            return error_response("Request body must be JSON", HTTP_400_BAD_REQUEST)

        try:
            from jsonschema import validate, ValidationError, FormatChecker  # pylint: disable=import-outside-toplevel
            validate(data, VERIFICATION_EXPIRE_SCHEMA, format_checker=FormatChecker())
        except ValidationError as exc:
            return error_response(exc.message, HTTP_400_BAD_REQUEST)

        if vr.status != "pending":
            return error_response(
                f"Request already has status '{vr.status}'", HTTP_400_BAD_REQUEST
            )

        vr.status = "expired"
        experience = db.session.get(Experience, vr.experience_id)
        experience.verification_status = "not_requested"
        db.session.commit()
        return jsonify(_serialize_vr_full(vr)), HTTP_200_OK


def _serialize_vr_full(vr):
    """
    Return a verification request dict with embedded experience and project context.

    Used by M2M endpoints so the reminder service has everything it needs
    (verifier email, token, position, company, requester name) in one response.
    """
    exp = vr.experience
    return {
        **vr.serialize(),
        "context": {
            "company_name": exp.company_name,
            "position_title": exp.position_title,
            "requester_username": exp.project.owner.username,
            "project_id": exp.project_id,
        },
    }


api_blueprint.add_url_rule(
    "/verification-requests/",
    view_func=VerificationRequestM2MCollection.as_view("verification_request_m2m_collection"),
    methods=["GET"],
)
api_blueprint.add_url_rule(
    "/verification-requests/<int:request_id>/",
    view_func=VerificationRequestM2MResource.as_view("verification_request_m2m_resource"),
    methods=["GET", "PATCH"],
)

api_blueprint.add_url_rule(
    "/users/<user:user>/projects/<project:project>/experiences/<experience:experience>/verification-requests/",
    view_func=ExperienceVerificationCollection.as_view(
        "experience_verification_collection"
    ),
    methods=["GET", "POST"],
)
api_blueprint.add_url_rule(
    "/users/<user:user>/projects/<project:project>/experiences/<experience:experience>/verification-requests/<vr:vr>/",
    view_func=VerificationRequestResource.as_view("verification_request_resource"),
    methods=["GET"],
)
api_blueprint.add_url_rule(
    "/verification-requests/<int:request_id>/respond/",
    view_func=VerificationRespondResource.as_view("verification_respond"),
    methods=["POST"],
)
