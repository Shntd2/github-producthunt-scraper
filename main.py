from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import logging
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from routes import root, trending, health, product_hunt_trending
from dependencies import get_scraper

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scraper = get_scraper()

    scraper._pre_resolve_domain()

    import asyncio
    asyncio.create_task(scraper.warm_cache())

    yield

    if hasattr(scraper, 'session'):
        scraper.session.close()
    if hasattr(scraper, 'executor'):
        scraper.executor.shutdown(wait=False)


app = FastAPI(
    title="GitHub Trending Scraper",
    description="Scrape GitHub trending repositories optimized for Glance dashboard",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(root.router)
app.include_router(trending.router)
app.include_router(health.router)
app.include_router(product_hunt_trending.router)

if __name__ == "__main__":
    import uvicorn

    APP_HOST = os.getenv("HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("PORT", 8000))

    uvicorn.run(
        app,
        host=APP_HOST,
        port=APP_PORT,
        access_log=True,
        reload=False,
        workers=1,
        loop="uvloop",
        limit_concurrency=1000,
        limit_max_requests=10000
    )
