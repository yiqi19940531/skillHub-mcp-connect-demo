from contextlib import asynccontextmanager
import logging
import uuid
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount

from backend.app.api.routes import create_routes
from backend.app.auth.identity import Identity
from backend.app.auth.oauth import router_for
from backend.app.config import ROOT, Settings
from backend.app.errors import HubError, failure, TRACE_ID
from backend.app.mcp.server import create_mcp
from backend.app.seed import seed
from backend.app.security.logging import protect_logs
from backend.app.security.headers import content_security_policy
from backend.app.services.hub import Hub


def create_app(settings=None):
    cfg = settings or Settings()
    hub = Hub(cfg)
    if cfg.seed_enabled:
        seed(hub)
    identity = Identity(hub)
    mcp = create_mcp(hub, identity)
    mcp_app = mcp.streamable_http_app(json_response=True, stateless_http=True)
    protect_logs()

    @asynccontextmanager
    async def lifespan(app):
        # Acquire a lifetime lock as well: a second process must not expire this process's tickets.
        from filelock import FileLock, Timeout

        process_lock = FileLock(str(cfg.data_dir / ".server.lock"))
        try:
            process_lock.acquire(timeout=0)
        except Timeout as exc:
            raise RuntimeError("同一个 DATA_DIR 只能运行一个服务进程") from exc
        identity.begin_boot()
        logging.getLogger("skillhub").warning("演示账号，仅绑定本机；禁止公网暴露。Web: %s/app", cfg.base_url)
        try:
            async with mcp.session_manager.run():
                yield
        finally:
            process_lock.release()

    app = FastAPI(
        title="Enterprise Skill Hub", version="1.1.0", lifespan=lifespan, docs_url="/api/docs", redoc_url=None
    )
    app.state.hub, app.state.identity, app.state.mcp = hub, identity, mcp

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        trace_id = uuid.uuid4().hex
        request.state.trace_id = trace_id
        try:
            host = urlsplit("http://" + request.headers.get("host", "")).hostname
        except ValueError:
            host = None
        if host not in {"127.0.0.1", "localhost", "::1"}:
            return JSONResponse({"error": "invalid_host"}, status_code=421)
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > cfg.max_zip + 65536):
            return JSONResponse(
                failure(HubError("REQUEST_TOO_LARGE", "请求超过大小限制", 413), trace_id), status_code=413
            )
        context_token = TRACE_ID.set(trace_id)
        try:
            response = await call_next(request)
        finally:
            TRACE_ID.reset(context_token)
        response.headers.update(
            {
                "X-Request-ID": trace_id,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Cache-Control": "no-store",
            }
        )
        response.headers.setdefault("Content-Security-Policy", content_security_policy())
        return response

    @app.exception_handler(HubError)
    async def domain_error(request, error):
        headers = (
            {
                "WWW-Authenticate": f'Bearer resource_metadata="{cfg.base_url}/.well-known/oauth-protected-resource/mcp"'
            }
            if error.status == 401
            else {}
        )
        return JSONResponse(
            failure(error, getattr(request.state, "trace_id", None)),
            status_code=error.status,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Never echo passwords, Skill bodies, tokens or uploaded content from Pydantic's input field.
        return JSONResponse(
            failure(
                HubError("INVALID_INPUT", "请求字段或格式无效，请检查填写内容", 422),
                getattr(request.state, "trace_id", None),
            ),
            status_code=422,
        )

    @app.get("/healthz")
    def health():
        return {"status": "ok", "version": "1.1.0", "storage": "local-json", "mcp": "/mcp"}

    app.include_router(router_for(hub, identity))
    public, api = create_routes(hub, identity)
    app.include_router(public)
    app.include_router(api)
    distribution = ROOT / "frontend" / "dist"
    if (distribution / "assets").exists():
        app.mount("/assets", StaticFiles(directory=distribution / "assets"), name="assets")

    @app.get("/")
    def root():
        from fastapi.responses import RedirectResponse

        return RedirectResponse("/app")

    @app.get("/app")
    @app.get("/app/{page:path}")
    def frontend(page=""):
        if not (distribution / "index.html").exists():
            return JSONResponse({"message": "请先在 frontend 运行 npm ci && npm run build"}, status_code=503)
        return FileResponse(distribution / "index.html", media_type="text/html")

    app.router.routes.append(Mount("/", app=mcp_app))
    return app


def app_factory():
    return create_app()
