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

logging.basicConfig(
    level=logging.getLevelName(settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    logger.info("Starting background tasks...")
    await start_background_tasks(app)

    yield

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

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="http://localhost(:[0-9]+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    await ws_endpoint(websocket)


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
client_dist_path = os.path.join(project_root, "client", "dist")

if os.path.exists(client_dist_path):
    logger.info(f"Serving static frontend files from: {client_dist_path}")
    
    assets_path = os.path.join(client_dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/{fallback_path:path}")
    async def spa_fallback(fallback_path: str):
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
