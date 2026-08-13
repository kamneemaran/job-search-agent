"""Supabase client helpers for authenticated requests."""
import os
import base64
import json
import time
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")


class DecodedUser:
    def __init__(self, user_id: str, email: str = ""):
        self.id = user_id
        self.email = email


def decode_token(authorization: str | None) -> dict | None:
    """Locally decode and validate JWT token expiration. Returns payload dict or None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # Add proper padding for base64 decoding
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        
        # Check expiration
        exp = payload.get("exp")
        if exp and exp < int(time.time()):
            return None # Expired
            
        return payload
    except Exception:
        return None


def get_user_client(authorization: str | None = None) -> Client:
    """Create a Supabase client scoped to the authenticated user."""
    anon_key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
    client_key = anon_key or SUPABASE_SERVICE_KEY
    sb = create_client(SUPABASE_URL, client_key)

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            sb.auth.set_session(access_token=token, refresh_token="")
        except Exception:
            pass
    return sb


def get_user_id(authorization: str | None) -> str | None:
    """Extract user ID from auth token. Returns None if not authenticated."""
    payload = decode_token(authorization)
    if payload:
        return payload.get("sub")
    return None
