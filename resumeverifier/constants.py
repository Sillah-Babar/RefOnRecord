"""HTTP status codes, JSON schemas, and error helper."""
from flask import jsonify

HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_204_NO_CONTENT = 204
HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_403_FORBIDDEN = 403
HTTP_404_NOT_FOUND = 404
HTTP_409_CONFLICT = 409

USER_REGISTER_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {"type": "string", "format": "email", "maxLength": 255},
        "username": {"type": "string", "minLength": 3, "maxLength": 100},
        "password": {"type": "string", "minLength": 8, "maxLength": 128},
        "phone_number": {"type": "string", "maxLength": 20},
        "tier": {"type": "string", "enum": ["normal", "premium"]},
    },
    "required": ["email", "username", "password"],
    "additionalProperties": False,
}

USER_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {"type": "string", "format": "email", "maxLength": 255},
        "username": {"type": "string", "minLength": 3, "maxLength": 100},
        "phone_number": {"type": "string", "maxLength": 20},
        "tier": {"type": "string", "enum": ["normal", "premium"]},
    },
    "additionalProperties": False,
    "minProperties": 1,
}

LOGIN_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {"type": "string", "format": "email"},
        "password": {"type": "string"},
    },
    "required": ["email", "password"],
    "additionalProperties": False,
}

PROJECT_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "project_name": {"type": "string", "minLength": 1, "maxLength": 200},
        "template_style": {"type": "string", "enum": ["classic", "modern", "minimal"]},
        "phone_number": {"type": "string", "maxLength": 20},
        "linkedin_url": {"type": "string", "maxLength": 500},
        "github_url": {"type": "string", "maxLength": 500},
        "personal_website": {"type": "string", "maxLength": 500},
        "current_company": {"type": "string", "maxLength": 200},
        "is_employed": {"type": "boolean"},
        "education_details": {"type": "string"},
    },
    "required": ["project_name"],
    "additionalProperties": False,
}

PROJECT_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "project_name": {"type": "string", "minLength": 1, "maxLength": 200},
        "template_style": {"type": "string", "enum": ["classic", "modern", "minimal"]},
        "phone_number": {"type": "string", "maxLength": 20},
        "linkedin_url": {"type": "string", "maxLength": 500},
        "github_url": {"type": "string", "maxLength": 500},
        "personal_website": {"type": "string", "maxLength": 500},
        "current_company": {"type": "string", "maxLength": 200},
        "is_employed": {"type": "boolean"},
        "education_details": {"type": "string"},
    },
    "additionalProperties": False,
    "minProperties": 1,
}

EXPERIENCE_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string", "minLength": 1, "maxLength": 200},
        "position_title": {"type": "string", "minLength": 1, "maxLength": 200},
        "start_date": {"type": "string", "format": "date"},
        "end_date": {"type": ["string", "null"], "format": "date"},
        "description": {"type": "string", "minLength": 1},
    },
    "required": ["company_name", "position_title", "start_date", "description"],
    "additionalProperties": False,
}

EXPERIENCE_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string", "minLength": 1, "maxLength": 200},
        "position_title": {"type": "string", "minLength": 1, "maxLength": 200},
        "start_date": {"type": "string", "format": "date"},
        "end_date": {"type": ["string", "null"], "format": "date"},
        "description": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
    "minProperties": 1,
}

VERIFICATION_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "verifier_name": {"type": "string", "minLength": 1, "maxLength": 200},
        "verifier_position": {"type": "string", "minLength": 1, "maxLength": 200},
        "verifier_email": {"type": "string", "format": "email", "maxLength": 255},
    },
    "required": ["verifier_name", "verifier_position", "verifier_email"],
    "additionalProperties": False,
}

VERIFICATION_RESPOND_SCHEMA = {
    "type": "object",
    "properties": {
        "verification_token": {"type": "string"},
        "status": {"type": "string", "enum": ["verified", "rejected"]},
        "verifier_comment": {"type": "string"},
    },
    "required": ["verification_token", "status"],
    "additionalProperties": False,
}

SHARE_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "recipient_email": {"type": "string", "format": "email", "maxLength": 255},
        "access_type": {"type": "string", "enum": ["view", "edit"]},
        "email_subject": {"type": "string", "maxLength": 500},
        "email_message": {"type": "string"},
        "expires_at": {"type": "string", "format": "date-time"},
    },
    "additionalProperties": False,
}


def error_response(message, status_code):
    """Return a JSON error response tuple."""
    return jsonify({"error": message}), status_code
