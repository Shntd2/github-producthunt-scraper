from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from dotenv import load_dotenv

from routes import root, trending, health

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GitHub Trending Scraper",
    description="Scrape GitHub trending repositories optimized for Glance dashboard",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(root.router)
app.include_router(trending.router)
app.include_router(health.router)


if __name__ == "__main__":
    import uvicorn
    APP_HOST = os.getenv("HOST")
    APP_PORT = int(os.getenv("PORT"))

    uvicorn.run(
        app,
        host=APP_HOST,
        port=APP_PORT,
        access_log=True,
        reload=False
    )
