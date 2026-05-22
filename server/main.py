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

# Setup logging
logging.basicConfig(
    level=logging.getLevelName(settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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

# CORS middleware for local frontend dev server (default port 5173 for Vite)
app.add_middleware(
    CORSMiddleware,
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


# Serve Static Frontend Files (client/dist) in production/Render environment
# This allows the backend to host the compiled React app on the same port.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
client_dist_path = os.path.join(project_root, "client", "dist")

if os.path.exists(client_dist_path):
    logger.info(f"Serving static frontend files from: {client_dist_path}")
    
    # Mount assets folder for bundle loads
    assets_path = os.path.join(client_dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    # Catch-all route to serve the Single Page Application index.html
    @app.get("/{fallback_path:path}")
    async def spa_fallback(fallback_path: str):
        # Do not hijack API or websocket paths
        if fallback_path.startswith("api/") or fallback_path == "ws":
            return None
            
        index_file = os.path.join(client_dist_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"detail": "Frontend assets compiled, but index.html is missing."}
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
