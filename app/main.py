from contextlib import asynccontextmanager
from pathlib import Path
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db, seed_keywords, seed_sources
from app import config
from app.routes import rating, admin, dismiss, api
from app.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    seed_keywords(config.get("keyword_weights", {}))
    seed_sources(config.get("sources", {}))

    scheduler = setup_scheduler(app)
    scheduler.start()
    logger.info("Scheduler started. Daily fetch at %s", config.get("schedule.fetch_time"))

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(title="AI News Tracker", lifespan=lifespan)

# Routes
app.include_router(rating.router)
app.include_router(admin.router)
app.include_router(dismiss.router)
app.include_router(api.router)

# Serve React SPA in production (site/dist must exist from `npm run build`)
spa_dir = Path(__file__).parent.parent / "site" / "dist"
if spa_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(spa_dir / "assets")), name="spa-assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Catch-all: serve index.html for client-side routing."""
        file = spa_dir / path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(spa_dir / "index.html")
