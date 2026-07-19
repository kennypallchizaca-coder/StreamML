"""FastAPI app factory and ASGI entrypoint for StreamML online."""

from __future__ import annotations

# Uvicorn reload trigger
from contextlib import asynccontextmanager
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.config import Settings
from apps.api.routers import (
    auth,
    control,
    models,
    network,
    pairing,
    predictions,
    sessions,
    settings as settings_router,
    streams,
    telemetry,
    websockets,
)
from src.streamml.inference import InferenceEngine, OfficialModelRegistry
from src.streamml.agent import AutonomousStreamingAgent
from src.streamml.observability.logging import LOGGER, audit_log, configure_logging
from src.streamml.security.auth import normalize_email
from src.streamml.security.rate_limit import RateLimiter
from src.streamml.services.database import Database, LATEST_SCHEMA_VERSION
from src.streamml.services.session_store import SessionStore
from src.streamml.services.websocket_hub import WebSocketHub


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    registry = OfficialModelRegistry(config.root_dir)
    database = Database(config.database_path)
    websocket_hub = WebSocketHub()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        config.validate_runtime()
        database.initialize()
        database.cleanup_expired_credentials()
        if config.bootstrap_email and config.bootstrap_password:
            database.create_user_if_missing(normalize_email(config.bootstrap_email), config.bootstrap_password)
        try:
            yield
        finally:
            await websocket_hub.close()

    application = FastAPI(
        title="StreamML API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.settings = config
    application.state.database = database
    application.state.registry = registry
    application.state.engine = InferenceEngine(registry)
    application.state.agent = AutonomousStreamingAgent()
    application.state.session_store = SessionStore(database, registry)
    application.state.websocket_hub = websocket_hub
    application.state.rate_limiter = RateLimiter()
    configure_logging()

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-StreamML-Media-Secret", "X-Request-ID"],
    )

    @application.middleware("http")
    async def security_middleware(request: Request, call_next):
        started = time.perf_counter()
        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = (
            supplied_request_id if re.fullmatch(r"[A-Za-z0-9._-]{1,80}", supplied_request_id) else uuid.uuid4().hex
        )
        forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",", 1)[0].strip()
        internal_http_paths = {"/health", "/health/live", "/health/ready", "/api/v1/internal/mediamtx/auth"}
        if config.enforce_https and forwarded_proto != "https" and request.url.path not in internal_http_paths:
            return JSONResponse(status_code=400, content={"message": "HTTPS is required."})
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        if forwarded_proto == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        audit_log(
            "http.request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        errors = []
        for item in exc.errors():
            errors.append({"location": list(item.get("loc", ())), "message": item.get("msg", "Invalid input")})
        return JSONResponse(status_code=422, content={"message": "Invalid request.", "details": errors})

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        LOGGER.exception(
            "http.unhandled_error",
            extra={"event": "http.unhandled_error", "details": {"path": request.url.path}},
        )
        return JSONResponse(status_code=500, content={"message": "Internal server error."})

    def readiness() -> tuple[bool, dict]:
        database_ok = database.ping() and database.integrity_check()
        schema_version = database.schema_version()
        schema_ok = schema_version == LATEST_SCHEMA_VERSION
        ready = database_ok and schema_ok
        return ready, {
            "status": "ok" if ready else "degraded",
            "database": "ok" if database_ok else "unavailable",
            "schema_version": schema_version,
            "models": "verified",
            "release_version": registry.version,
            "environment": config.environment,
            "ready": ready,
            "production_ready": ready and config.production_controls_ready(),
        }

    @application.get("/health")
    def health() -> dict:
        return readiness()[1]

    @application.get("/health/live")
    def liveness() -> dict:
        return {"status": "ok"}

    @application.get("/health/ready")
    def ready() -> JSONResponse:
        is_ready, payload = readiness()
        return JSONResponse(status_code=200 if is_ready else 503, content=payload)

    for api_router in (
        auth.router,
        sessions.router,
        pairing.router,
        control.router,
        settings_router.router,
        settings_router.connector_router,
        network.router,
        telemetry.router,
        predictions.router,
        models.router,
        streams.router,
        websockets.router,
    ):
        application.include_router(api_router)
    return application


app = create_app()
