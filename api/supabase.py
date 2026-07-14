"""Supabase client helpers for authenticated requests."""
import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")


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
    if not authorization:
        return None
    try:
        sb = get_user_client(authorization)
        resp = sb.auth.get_user()
        user = resp.user if hasattr(resp, "user") else resp
        if hasattr(user, "id"):
            return user.id
        if isinstance(user, dict):
            return user.get("id")
        return getattr(user, "id", None)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in get_user_id: {e}")
        return None
