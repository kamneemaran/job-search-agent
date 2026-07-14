"""Freemium rate limiting and plan enforcement."""
import os
from datetime import date
from fastapi import HTTPException, Header
from typing import Optional

from api.supabase import get_user_client

# Plan limits
PLAN_LIMITS = {
    "free": {
        "searches_per_day": 5,
        "max_tracked_jobs": 25,
        "digest_frequency": ["weekly"],
        "max_results_per_search": 10,
        "max_companies": 5,  # only search 5 companies + job boards
    },
    "pro": {
        "searches_per_day": 50,
        "max_tracked_jobs": 500,
        "digest_frequency": ["daily", "weekly", "biweekly"],
        "max_results_per_search": 50,
        "max_companies": 50,
    },
    "enterprise": {
        "searches_per_day": -1,
        "max_tracked_jobs": -1,
        "digest_frequency": ["daily", "weekly", "biweekly"],
        "max_results_per_search": 50,
        "max_companies": -1,  # all
    },
}


def get_user_plan(authorization: Optional[str]) -> dict:
    """Get user's subscription plan and current usage.
    
    Returns dict with keys: plan, searches_today, tracker_count, limits
    """
    if not authorization:
        return {"plan": "free", "searches_today": 0, "tracker_count": 0, "limits": PLAN_LIMITS["free"]}

    try:
        sb = get_user_client(authorization)
        user = sb.auth.get_user().user

        result = sb.table("subscriptions").select("*").eq("user_id", user.id).maybe_single().execute()

        if not result.data:
            # Create default free subscription
            sb.table("subscriptions").insert({
                "user_id": user.id,
                "plan": "free",
                "searches_today": 0,
                "searches_reset_at": str(date.today()),
                "tracker_count": 0,
            }).execute()
            return {"plan": "free", "searches_today": 0, "tracker_count": 0, "limits": PLAN_LIMITS["free"]}

        row = result.data
        plan = row.get("plan", "free")
        searches_today = row.get("searches_today", 0)

        # Reset daily counter if date changed
        reset_at = row.get("searches_reset_at", "")
        if str(reset_at) != str(date.today()):
            searches_today = 0
            sb.table("subscriptions").update({
                "searches_today": 0,
                "searches_reset_at": str(date.today()),
            }).eq("user_id", user.id).execute()

        return {
            "plan": plan,
            "searches_today": searches_today,
            "tracker_count": row.get("tracker_count", 0),
            "limits": PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]),
        }
    except Exception:
        return {"plan": "free", "searches_today": 0, "tracker_count": 0, "limits": PLAN_LIMITS["free"]}


def check_search_limit(authorization: Optional[str]):
    """Check if user has remaining searches. Raises HTTPException if exceeded."""
    info = get_user_plan(authorization)
    limits = info["limits"]
    max_searches = limits["searches_per_day"]

    if max_searches == -1:
        return info  # unlimited

    if info["searches_today"] >= max_searches:
        raise HTTPException(
            429,
            f"Daily search limit reached ({max_searches} searches/day on {info['plan']} plan). "
            f"Upgrade to Pro for 50 searches/day."
        )
    return info


def increment_search_count(authorization: Optional[str]):
    """Increment the user's daily search counter."""
    if not authorization:
        return
    try:
        sb = get_user_client(authorization)
        user = sb.auth.get_user().user
        sb.rpc("increment_search_count", {"uid": user.id}).execute()
    except Exception:
        # Fallback: direct update
        try:
            sb = get_user_client(authorization)
            user = sb.auth.get_user().user
            result = sb.table("subscriptions").select("searches_today").eq("user_id", user.id).maybe_single().execute()
            if result.data:
                current = result.data.get("searches_today", 0)
                sb.table("subscriptions").update({"searches_today": current + 1}).eq("user_id", user.id).execute()
        except Exception:
            pass


def check_tracker_limit(authorization: Optional[str]):
    """Check if user can add more jobs to tracker. Raises HTTPException if exceeded."""
    info = get_user_plan(authorization)
    limits = info["limits"]
    max_tracked = limits["max_tracked_jobs"]

    if max_tracked == -1:
        return info  # unlimited

    if info["tracker_count"] >= max_tracked:
        raise HTTPException(
            429,
            f"Tracker limit reached ({max_tracked} jobs on {info['plan']} plan). "
            f"Upgrade to Pro for 500 tracked jobs."
        )
    return info


def get_max_results(authorization: Optional[str]) -> int:
    """Get the max results per search for the user's plan."""
    info = get_user_plan(authorization)
    return info["limits"]["max_results_per_search"]


def get_max_companies(authorization: Optional[str]) -> int:
    """Get the max companies to search for the user's plan."""
    info = get_user_plan(authorization)
    return info["limits"].get("max_companies", 5)
