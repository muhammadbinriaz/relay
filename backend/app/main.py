import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import auth as auth_routes
from app.api import workflows as workflow_routes
from app.config import get_settings
from app.db import SessionLocal
from app.schemas import HealthOut
from app.services.queue import ping_redis

settings = get_settings()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("relay.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("relay_api_starting")
    yield
    logger.info("relay_api_stopping")


app = FastAPI(
    title="Relay",
    description="Durable workflow engine — control plane API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_log(request: Request, call_next):
    response = await call_next(request)
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
        },
    )
    return response


app.include_router(auth_routes.router)
app.include_router(workflow_routes.router)


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False
    redis_ok = ping_redis()
    status = "ok" if db_ok and redis_ok else "degraded"
    return HealthOut(
        status=status,
        service="relay-api",
        version="0.1.0",
        redis="ok" if redis_ok else "down",
        database="ok" if db_ok else "down",
    )


@app.get("/api/metrics")
def metrics():
    from app.services.queue import get_redis

    client = get_redis()
    keys = [
        "runs_created",
        "runs_completed",
        "steps_completed",
        "steps_retried",
        "approvals_requested",
        "approvals_decided",
        "dead_letters",
    ]
    data = {k: int(client.get(f"relay:metrics:{k}") or 0) for k in keys}
    return {"metrics": data}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.exception("unhandled_error path=%s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
