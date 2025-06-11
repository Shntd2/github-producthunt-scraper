from fastapi import APIRouter
from datetime import datetime
from config import settings

router = APIRouter(
    tags=["root"]
)


@router.get("/")
async def root():
    return {
        "message": f"{settings.APP_NAME} - Optimized for Glance",
        "version": settings.APP_VERSION,
        "description": settings.APP_DESCRIPTION,
        "endpoints": {
            "github-trending": "/trending",
            "health": "/health",
            "producthunt-stories": "/product-hunt/stories"
        },
        "glance_ready": True,
        "timestamp": datetime.now().isoformat()
    }
