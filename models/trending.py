from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Contributor(BaseModel):
    username: str = Field(..., description="GitHub username")
    avatar_url: str = Field(..., description="URL to user's avatar image")


class Repository(BaseModel):
    name: str = Field(..., description="Repository name with owner")
    url: str = Field(..., description="GitHub repository URL")
    owner: Optional[str] = Field(None, description="Repository owner username")
    repository: Optional[str] = Field(None, description="Repository name")
    description: str = Field("", description="Repository description")
    language: Optional[str] = Field(None, description="Primary programming language")
    language_color: str = Field("#586069", description="Color associated with the language")
    stars: int = Field(0, description="Total number of stars")
    forks: Optional[int] = Field(0, description="Total number of forks")
    stars_today: Optional[int] = Field(0, description="Stars gained today")
    contributors: List[Contributor] = Field(default_factory=list, description="Top contributors")


class TrendingResponse(BaseModel):
    repositories: List[Repository] = Field(..., description="List of trending repositories")
    count: int = Field(..., description="Number of repositories returned")
    language: Optional[str] = Field(None, description="Language filter applied")
    since: str = Field("daily", description="Time period for trending")
    updated_at: str = Field(..., description="Timestamp when data was last updated")
    error: Optional[str] = Field(None, description="Error message if fallback data is used")

    class Config:
        json_schema_extra = {
            "example": {
                "repositories": [
                    {
                        "name": "microsoft/TypeScript",
                        "url": "https://github.com/microsoft/TypeScript",
                        "owner": "microsoft",
                        "repository": "TypeScript",
                        "description": "TypeScript is a superset of JavaScript that compiles to clean JavaScript output.",
                        "language": "TypeScript",
                        "language_color": "#2b7489",
                        "stars": 95000,
                        "forks": 12000,
                        "stars_today": 150,
                        "contributors": [
                            {
                                "username": "ahejlsberg",
                                "avatar_url": "https://avatars.githubusercontent.com/u/4226..."
                            }
                        ]
                    }
                ],
                "count": 1,
                "language": "typescript",
                "since": "daily",
                "updated_at": "2025-06-05T12:00:00.000Z"
            }
        }
