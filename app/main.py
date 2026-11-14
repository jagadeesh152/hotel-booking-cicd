import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.config import settings
from app.database import init_db
from app.logging_conf import setup_logging
from app.routes import router

setup_logging(settings.log_level)
log = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    log.info("application started", extra={"version": settings.app_version})
    yield
    log.info("application stopping")


app = FastAPI(title="Hotel Booking API", version=settings.app_version, lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    log.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        },
    )
    return response


app.include_router(router)
