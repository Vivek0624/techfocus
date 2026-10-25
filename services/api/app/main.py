from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agents.orchestrator import Orchestrator
from .config import get_settings
from .db import SessionLocal
from .instagram.client import InstagramClient
from .logging_conf import configure_logging
from .routers import activity, agents_ig, content, core, creator, growth, interests
from .security import require_api_auth
from .seed import seed_agents, seed_demo

log = logging.getLogger("api")


def _origins(origin: str) -> list[str]:
    """Browsers treat localhost and 127.0.0.1 as different origins; allow both for the same port."""
    alts = {
        origin,
        origin.replace("://localhost", "://127.0.0.1"),
        origin.replace("://127.0.0.1", "://localhost"),
    }
    return sorted(alts)


def create_app(
    session_factory=SessionLocal,
    orchestrator: Orchestrator | None = None,
    client_factory=None,
    seed: bool = True,
) -> FastAPI:
    s = get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if seed:
            with session_factory() as db:
                seed_agents(db)
                seed_demo(db)
                db.commit()
        sched = None
        if s.enable_local_scheduler:
            from .scheduler import start_scheduler

            sched = start_scheduler(session_factory, app.state.instagram_client_factory)
        yield
        if sched:
            sched.shutdown(wait=False)

    app = FastAPI(
        title="Vivek TechFocus Growth Manager API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.orchestrator = orchestrator or Orchestrator(session_factory, s)
    app.state.instagram_client_factory = client_factory or (lambda tok, uid: InstagramClient(s, tok, uid))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins(s.web_origin),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        t0 = time.monotonic()
        response = await call_next(request)
        log.info(
            "request",
            extra={
                "request_id": rid,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )
        response.headers["x-request-id"] = rid
        return response

    @app.exception_handler(HTTPException)
    async def http_err(_: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, (str, dict)) else str(exc.detail)
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def val_err(_: Request, exc: RequestValidationError):
        errs = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse({"error": "validation failed", "details": errs}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse({"error": "internal error"}, status_code=500)  # no stack traces to clients

    deps = [Depends(require_api_auth)]
    for r in (
        core.router,
        content.router,
        agents_ig.router,
        creator.router,
        activity.router,
        growth.router,
        interests.router,
    ):
        app.include_router(r, prefix="/api", dependencies=deps)
        app.include_router(r, prefix="/api/v1", dependencies=deps, include_in_schema=False)
    return app


app = create_app()
