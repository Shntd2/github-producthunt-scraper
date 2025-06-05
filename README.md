# GitHub Trending Scraper

A FastAPI-based web scraper for GitHub trending repositories, optimized for [Glance](https://github.com/glanceapp/glance) dashboard integration

## Features
- **Trending Data**: Scrapes GitHub trending repositories
- **Caching**: In-memory caching for improved performance
- **Configurable**: Environment-based configuration
- **Scalable Architecture**: Organized with APIRouter pattern

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd github-trending-scraper
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your preferred settings
HOST=0.0.0.0
PORT=8000
DEBUG=False

LOG_LEVEL=INFO

CACHE_TIMEOUT=600
MAX_WORKERS=2
REQUEST_TIMEOUT=8
MAX_REPOSITORIES=15

POOL_CONNECTIONS=10
POOL_MAXSIZE=10
MAX_RETRIES=0
POOL_BLOCK=False
```

### 3. Run the Application

```bash
# Development
python main.py

# With auto-reload for development
uvicorn main:app --reload
```

## API Endpoints

### GET `/`
Root endpoint with API information.

### GET `/trending`
Get trending GitHub repositories.

**Parameters:**
- `language` (optional): Programming language filter (e.g., "python", "javascript")
- `since` (optional): Time period - "daily", "weekly", or "monthly" (default: "daily")

**Example:**
```bash
curl "http://localhost:8000/trending?language=python&since=weekly"
```

## Response Format

### Trending Response
```json
{
  "repositories": [
    {
      "name": "microsoft/TypeScript",
      "url": "https://github.com/microsoft/TypeScript",
      "owner": "microsoft",
      "repository": "TypeScript",
      "description": "TypeScript is a superset of JavaScript...",
      "language": "TypeScript",
      "language_color": "#2b7489",
      "stars": 95000,
      "forks": 12000,
      "stars_today": 150,
      "contributors": [
        {
          "username": "ahejlsberg",
          "avatar_url": "https://avatars.githubusercontent.com/u/..."
        }
      ]
    }
  ],
  "count": 1,
  "language": "typescript",
  "since": "daily",
  "updated_at": "2025-06-05T12:00:00.000Z",
  "cached": true
}
```