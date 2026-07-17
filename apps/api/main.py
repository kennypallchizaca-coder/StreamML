"""FastAPI app factory and ASGI entrypoint for StreamML online."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.config import Settings
from apps.api.routers import auth, models, pairing, predictions, sessions, streams, telemetry, websockets
from src.streamml.inference import InferenceEngine, OfficialModelRegistry
from src.streamml.observability.logging import configure_logging
from src.streamml.security.auth import normalize_email
from src.streamml.security.rate_limit import RateLimiter
from src.streamml.services.database import Database
from src.streamml.services.session_store import SessionStore
from src.streamml.services.websocket_hub import WebSocketHub


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    registry = OfficialModelRegistry(config.root_dir)
    database = Database(config.database_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        config.validate_runtime()
        database.initialize()
        if config.bootstrap_email and config.bootstrap_password:
            database.create_user_if_missing(normalize_email(config.bootstrap_email), config.bootstrap_password)
        yield

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
    application.state.session_store = SessionStore(database, registry)
    application.state.websocket_hub = WebSocketHub()
    application.state.rate_limiter = RateLimiter()
    configure_logging()

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-StreamML-Media-Secret"],
    )

    @application.middleware("http")
    async def security_middleware(request: Request, call_next):
        forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",", 1)[0].strip()
        internal_http_paths = {"/health", "/api/v1/internal/mediamtx/auth"}
        if config.enforce_https and forwarded_proto != "https" and request.url.path not in internal_http_paths:
            return JSONResponse(status_code=400, content={"message": "HTTPS is required."})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        errors = []
        for item in exc.errors():
            errors.append({"location": list(item.get("loc", ())), "message": item.get("msg", "Invalid input")})
        return JSONResponse(status_code=422, content={"message": "Invalid request.", "details": errors})

    @application.get("/health")
    def health() -> dict:
        return {
            "status": "ok" if database.ping() else "degraded",
            "database": "ok" if database.ping() else "unavailable",
            "models": "verified",
            "release_version": registry.version,
            "production_ready": False,
        }

    for api_router in (
        auth.router, sessions.router, pairing.router, telemetry.router, predictions.router,
        models.router, streams.router, websockets.router,
    ):
        application.include_router(api_router)
    return application


app = create_app()
