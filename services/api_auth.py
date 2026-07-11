"""
JWT authentication for the JSON API (/api/v1).

Two access paths:
  - Bearer token (Authorization: Bearer <jwt>) — issued by POST /api/v1/auth/token,
    HS256-signed with the app SECRET_KEY. Works from any client (mobile, scripts).
  - Browser session (Flask-Login cookie) — accepted on READ endpoints only.

Write endpoints require a Bearer token. The API blueprint is CSRF-exempt, and a
session cookie is sent automatically by browsers — accepting it on writes would
reopen CSRF. A Bearer header can't be forged cross-site, so writes stay safe.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request
from flask_login import current_user
from flask_smorest import abort

from models import User


def issue_token(user):
    """Create a signed access token for a user."""
    ttl = int(current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES", 86400))
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
    }
    token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "expires_in": ttl}


def _user_from_bearer():
    """Resolve the Authorization: Bearer header to a User, or None."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer "):].strip()
    try:
        payload = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    user = User.query.get(int(payload["sub"]))
    if user is None or user.is_banned or not user.is_active:
        return None
    return user


def resolve_api_user(allow_session=True):
    """Current API caller: Bearer token first, then (optionally) the session."""
    user = _user_from_bearer()
    if user is None and allow_session and current_user.is_authenticated:
        if not current_user.is_banned:
            user = current_user
    return user


def auth_required(write=False):
    """Protect an API endpoint. write=True → Bearer token only (see module doc)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = resolve_api_user(allow_session=not write)
            if user is None:
                abort(401, message=(
                    "Bearer token required. Get one via POST /api/v1/auth/token."
                    if write else "Authentication required."
                ))
            g.api_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator
