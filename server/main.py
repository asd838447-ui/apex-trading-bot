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
from fastapi.responses import FileResponse

from server.config import settings
from server.db.database import init_db, close_db
from server.api.routes import router as api_router
from server.api.ws import ws_endpoint
from server.tasks.scheduler import start_background_tasks, stop_background_tasks

from starlette.exceptions import HTTPException as StarletteHTTPException

# Setup logging
logging.basicConfig(
    level=logging.getLevelName(settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    """
    Custom StaticFiles wrapper that catches 404 errors and falls back to index.html
    for client-side Single Page Application (SPA) routing.
    """
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
    # Startup safety checks
    logger.info("Running system startup validation...")
    if not settings.DEMO_MODE:
        jwt_secret = settings.JWT_SECRET_KEY
        if len(jwt_secret) < 32 or "change-me" in jwt_secret.lower() or "changeme" in jwt_secret.lower():
            raise ValueError(
                "CRITICAL SECURITY ERROR: In combat mode (DEMO_MODE=False), "
                "JWT_SECRET_KEY must be at least 32 characters long and cannot be a default placeholder."
            )
        logger.info("  ✓ JWT Secret Key validated successfully for Live Combat mode.")
    else:
        logger.info("  ✓ Running in DEMO/Simulation mode (security validation bypassed).")

    logger.info("Initializing database...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Proceed anyway if fallback DB handles it

    logger.info("Starting background tasks...")
    await start_background_tasks(app)

    yield

    # Shutdown
    logger.info("Stopping background tasks...")
    await stop_background_tasks()

    logger.info("Closing database...")
    await close_db()


app = FastAPI(
    title="APEX Trading Bot API",
    description="Backend API Gateway for APEX Algorithmic Trading Bot",
    version="1.0.0",
    lifespan=lifespan,
)

# Wire CORS origins
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

# Mount REST API Router
app.include_router(api_router)


# Mount WebSocket Route
@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    await ws_endpoint(websocket)


@app.get("/health")
async def root_health_check():
    """Direct, lightweight health check endpoint for Render blueprint routing."""
    return {"status": "ok"}


# Serve Static Frontend Files (client/dist) in production/Render environment
# This allows the backend to host the compiled React app on the same port.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
client_dist_path = os.path.join(project_root, "client", "dist")

if os.path.exists(client_dist_path):
    logger.info(f"Serving static frontend files from: {client_dist_path}")
    
    # Mount SPA Static Files at / as the very last route definition
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
