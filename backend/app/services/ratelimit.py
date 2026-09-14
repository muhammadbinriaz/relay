"""Simple Redis fixed-window rate limiter for sensitive routes."""

from __future__ import annotations

import time

from fastapi import HTTPException, Request, status

from app.services.queue import get_redis


def rate_limit(request: Request, *, key: str, limit: int, window_seconds: int = 60) -> None:
    client_ip = request.client.host if request.client else "unknown"
    bucket = int(time.time() // window_seconds)
    redis_key = f"relay:rl:{key}:{client_ip}:{bucket}"
    try:
        redis = get_redis()
        count = int(redis.incr(redis_key))
        if count == 1:
            redis.expire(redis_key, window_seconds + 1)
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({limit}/{window_seconds}s). Try again shortly.",
            )
    except HTTPException:
        raise
    except Exception:
        # Fail open if Redis is briefly unavailable — health will show degraded.
        return
