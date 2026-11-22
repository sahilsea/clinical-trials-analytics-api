"""FastAPI application entry point: `uvicorn app.main:app --reload`."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.api.routes import analytics, system, trials
from app.config import get_settings
from app.database import init_db

logger = logging.getLogger("app")

DESCRIPTION = """
REST API over ~5,800 COVID-19 clinical trials registered on ClinicalTrials.gov.

* **Trials**: search, filter, sort and paginate; create/update/delete with an API key.
* **Analytics**: summary stats, distributions, top countries, timelines, age groups.
* **System**: health check and ETL run history.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logger.info("Database ready")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        """Attach a request ID and timing header, and log one line per request."""
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
        logger.info(
            "%s %s -> %s (%.1f ms) id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.exception("Database error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=503, content={"detail": "Database error"})

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/docs")

    app.include_router(system.router)
    app.include_router(trials.router, prefix="/api/v1")
    app.include_router(analytics.router, prefix="/api/v1")
    return app


app = create_app()
