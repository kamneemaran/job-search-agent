"""Supabase client helpers for authenticated requests."""
from supabase import create_client, Client

SUPABASE_URL = __import__("os").environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = __import__("os").environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def get_user_client(authorization: str | None = None) -> Client:
    """Create a Supabase client scoped to the authenticated user.

    Uses the anon key + user's JWT so RLS policies apply.
    Falls back to service role key if no auth header.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        sb = create_client(SUPABASE_URL, __import__("os").environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""))
        sb.auth.set_session(access_token=token, refresh_token="")
        return sb

    # Service role fallback (for internal use / email digest)
    if SUPABASE_SERVICE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    raise ValueError("No authorization provided and no service role key configured")
