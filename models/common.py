from pydantic import BaseModel, Field
from typing import Dict, Any, List


class CacheInfo(BaseModel):
    cached_entries: int = Field(..., description="Number of cached entries")
    cache_keys: List[str] = Field(..., description="List of cache keys")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status")
    timestamp: str = Field(..., description="Current timestamp")
    version: str = Field(..., description="Application version")
    cache: Dict[str, Any] = Field(..., description="Cache information")
    config: Dict[str, Any] = Field(..., description="Configuration details")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-06-05T12:00:00.000Z",
                "version": "2.0.0",
                "cache": {
                    "cached_entries": 3,
                    "cache_keys": ["python_daily", "javascript_weekly", "all_daily"]
                },
                "config": {
                    "cache_timeout": 600,
                    "max_workers": 2,
                    "request_timeout": 8,
                    "max_repositories": 15
                }
            }
        }


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    detail: str = Field(..., description="Detailed error information")
    timestamp: str = Field(..., description="Error timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Bad Request",
                "detail": "Invalid language parameter",
                "timestamp": "2025-06-05T12:00:00.000Z"
            }
        }
