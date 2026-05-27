"""
APEX Trading Bot — FastAPI Main Application Entry Point
Initializes the web server, mounts API routes, WebSocket endpoint, background tasks scheduler,
and serves the React SPA from client/dist when built.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, ORJSONResponse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

from server.config import settings
from server.db.database import init_db, close_db
from server.api.routes import router as api_router
from server.api.ws import ws_endpoint
from server.tasks.scheduler import start_background_tasks, stop_background_tasks

from starlette.exceptions import HTTPException as StarletteHTTPException

logging.basicConfig(
    level=logging.getLevelName(settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> FileResponse:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as ex:
            if ex.status_code == 404:
                index_file = os.path.join(self.directory, "index.html")
                if os.path.exists(index_file):
                    return FileResponse(index_file)
            raise ex


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Running system startup validation...")
    
    jwt_secret = settings.JWT_SECRET_KEY
    if len(jwt_secret) < 32 or "change-me" in jwt_secret.lower() or "changeme" in jwt_secret.lower():
        raise ValueError(
            "CRITICAL SECURITY ERROR: JWT_SECRET_KEY must be at least 32 characters long "
            "and cannot be a default placeholder."
        )
    logger.info("  ✓ JWT Secret Key validated successfully for Live Combat mode.")

    vault_key = settings.VAULT_ENCRYPTION_KEY
    if not vault_key or len(vault_key) < 16 or "change-me" in vault_key.lower() or "changeme" in vault_key.lower():
        logger.warning(
            "SECURITY WARNING: VAULT_ENCRYPTION_KEY is empty, short or uses a default placeholder. "
            "If any secure storage/vault integration is added in the future, please provide a secure 32-character key."
        )
    else:
        logger.info("  ✓ Vault Encryption Key validated successfully.")

    logger.info("Initializing database...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    logger.info("Starting background tasks...")
    app.state.quant_alphas_data = {}
    await start_background_tasks(app)

    yield

    logger.info("Stopping background tasks...")
    await stop_background_tasks()

    logger.info("Closing database...")
    await close_db()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://* wss://*;"
            " img-src 'self' data: https:;"
        )
        return response


app = FastAPI(
    title="APEX Trading Bot API",
    description="Backend API Gateway for APEX Algorithmic Trading Bot",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)

if not settings.DEBUG and os.environ.get("RENDER"):
    app.add_middleware(HTTPSRedirectMiddleware)

origins = ["http://localhost:5173", "http://localhost:3000"]
if settings.CORS_ORIGINS:
    origins.extend([o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex="http://localhost(:[0-9]+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    await ws_endpoint(websocket)


@app.get("/health")
async def root_health_check():
    return {"status": "ok"}


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
client_dist_path = os.path.join(project_root, "client", "dist")

if os.path.exists(client_dist_path):
    logger.info(f"Serving static frontend files from: {client_dist_path}")
    
    app.mount("/", SPAStaticFiles(directory=client_dist_path, html=True), name="static")
else:
    logger.warning(
        f"Frontend build folder not found at: {client_dist_path}\n"
        "Frontend will not be served by this FastAPI instance. "
        "Run 'cd client && npm install && npm run build' to compile it."
    )

    @app.get("/")
    async def root_fallback():
        return {
            "message": "APEX Trading Bot API is running.",
            "frontend_status": "Not served (client/dist folder missing)",
            "docs": "/docs",
        }