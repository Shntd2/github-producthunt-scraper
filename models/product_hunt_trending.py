from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Story(BaseModel):
    title: str = Field(..., description="Story title")
    url: str = Field(..., description="Story URL")
    description: str = Field("", description="Story description or excerpt")
    author: str = Field("Unknown", description="Story author")
    author_url: Optional[str] = Field(None, description="Author profile URL (LinkedIn)")
    category: Optional[str] = Field(None, description="Story category")
    published_at: Optional[str] = Field(None, description="Publication date/time")
    read_time: Optional[int] = Field(None, description="Estimated read time in minutes")
    tags: List[str] = Field(default_factory=list, description="Story tags or categories")
    thumbnail_url: Optional[str] = Field(None, description="Story thumbnail image URL")
    upvotes: int = Field(0, description="Number of upvotes")
    story_id: Optional[str] = Field(None, description="Story ID from Product Hunt")


class ProductHuntTrendingResponse(BaseModel):
    stories: List[Story] = Field(..., description="List of trending stories")
    count: int = Field(..., description="Number of stories returned")
    category: Optional[str] = Field(None, description="Category filter applied")
    updated_at: str = Field(..., description="Timestamp when data was last updated")
    cached: Optional[bool] = Field(False, description="Whether the data is from cache")
    partial: Optional[bool] = Field(False, description="Whether partial data is returned")
    message: Optional[str] = Field(None, description="Additional message about the response")
    error: Optional[str] = Field(None, description="Error message if fallback data is used")

    class Config:
        json_schema_extra = {
            "example": {
                "stories": [
                    {
                        "title": "The inner work of startup building",
                        "url": "https://www.producthunt.com/stories/the-inner-work-of-startup-building",
                        "description": "",
                        "author": "Keegan Walden",
                        "author_url": "https://www.linkedin.com/in/keegan-walden-ph-d-672ab9101/",
                        "category": "Makers",
                        "published_at": None,
                        "read_time": 7,
                        "tags": ["Makers"],
                        "thumbnail_url": "https://ph-files.imgix.net/bc57c4b8-2a96-4b2f-a901-0c2d52b72b9f.png?auto=compress&codec=mozjpeg&cs=strip&auto=format&w=384&h=226&fit=crop&frame=1",
                        "upvotes": 0,
                        "story_id": "13267"
                    }
                ],
                "count": 1,
                "category": None,
                "updated_at": "2025-06-05T12:00:00.000Z",
                "cached": False
            }
        }
