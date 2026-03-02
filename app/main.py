from contextlib import asynccontextmanager
from pathlib import Path
import logging

from fastapi import FastAPI

from fastapi.staticfiles import StaticFiles

from app.database import init_db, seed_keywords, seed_sources
from app import config
from app.routes import newspaper, rating, admin, dismiss
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

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routes
app.include_router(newspaper.router)
app.include_router(rating.router)
app.include_router(admin.router)
app.include_router(dismiss.router)
