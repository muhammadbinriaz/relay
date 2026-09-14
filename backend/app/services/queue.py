from __future__ import annotations

import logging
from typing import Any

import httpx
import redis

from app.config import get_settings

logger = logging.getLogger("relay.metrics")
settings = get_settings()


def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def enqueue_step(step_id: str) -> None:
    client = get_redis()
    client.lpush(settings.redis_queue_key, step_id)


def enqueue_steps(step_ids: list[str]) -> None:
    if not step_ids:
        return
    client = get_redis()
    client.lpush(settings.redis_queue_key, *step_ids)


def ping_redis() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        return False


def incr_metric(name: str, amount: int = 1) -> None:
    try:
        get_redis().incrby(f"relay:metrics:{name}", amount)
    except Exception:
        logger.debug("metric_incr_failed", extra={"metric": name})


async def post_slack(text: str, blocks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    url = settings.slack_webhook_url
    if not url:
        logger.info("slack_stub", extra={"text": text})
        return {"ok": True, "stub": True, "text": text}
    payload: dict[str, Any] = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return {"ok": True, "status_code": resp.status_code}
