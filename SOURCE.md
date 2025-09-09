## Tree for paipi
```
├── client.py
├── config.py
├── main.py
└── models.py
```

## File: client.py
```python
"""
OpenRouter AI client for generating PyPI-style search results.
"""

import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from .models import SearchResult, SearchResponse
from .config import config


class OpenRouterClient:
    """Client for interacting with OpenRouter AI service via OpenAI interface."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        """Initialize the OpenRouter client."""
        self.api_key = api_key or config.openrouter_api_key
        self.base_url = base_url or config.openrouter_base_url
        
        if not self.api_key:
            raise ValueError("OpenRouter API key is required")
            
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
    
    def search_packages(self, query: str, limit: int = 20) -> SearchResponse:
        """
        Search for Python packages using AI knowledge.
        
        Args:
            query: Search query for Python packages
            limit: Maximum number of results to return
            
        Returns:
            SearchResponse containing AI-generated package results
        """
        prompt = self._build_search_prompt(query, limit)
        
        try:
            response = self.client.chat.completions.create(
                model=config.default_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that knows about Python packages on PyPI. "
                                 "You should return realistic package information in the exact JSON format requested."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=4000,
            )
            
            content = response.choices[0].message.content
            if not content:
                return SearchResponse()
                
            # Parse the AI response and convert to our model
            return self._parse_ai_response(content, query)
            
        except Exception as e:
            # Return empty response on error but log it
            print(f"Error querying OpenRouter: {e}")
            return SearchResponse()
    
    def _build_search_prompt(self, query: str, limit: int) -> str:
        """Build the prompt for the AI to generate PyPI search results."""
        return f"""
Please search for Python packages related to: "{query}"

Return up to {limit} relevant Python packages in this exact JSON format:
{{
    "results": [
        {{
            "name": "package-name",
            "version": "1.0.0",
            "description": "Brief description of the package",
            "summary": "One-line summary",
            "author": "Author Name",
            "author_email": "author@example.com",
            "home_page": "https://github.com/author/package",
            "package_url": "https://pypi.org/project/package-name/",
            "keywords": "keyword1, keyword2",
            "license": "MIT",
            "classifiers": [
                "Development Status :: 4 - Beta",
                "Intended Audience :: Developers",
                "License :: OSI Approved :: MIT License",
                "Programming Language :: Python :: 3"
            ],
            "requires_python": ">=3.7",
            "project_urls": {{
                "Homepage": "https://github.com/author/package",
                "Repository": "https://github.com/author/package",
                "Documentation": "https://package.readthedocs.io/"
            }}
        }}
    ]
}}

Focus on real, popular Python packages that match the search query. Include accurate information about versions, authors, and descriptions. If you're not certain about specific details, provide reasonable defaults that match typical PyPI package patterns.
"""
    
    def _parse_ai_response(self, content: str, query: str) -> SearchResponse:
        """Parse the AI response and convert to SearchResponse model."""
        try:
            # Try to extract JSON from the response
            content = content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(content)
            
            # Convert to our models
            results = []
            for item in data.get("results", []):
                try:
                    result = SearchResult(**item)
                    results.append(result)
                except Exception as e:
                    print(f"Error parsing result item: {e}")
                    continue
            
            return SearchResponse(
                info={"query": query, "count": len(results)},
                results=results
            )
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Content: {content}")
            return SearchResponse()
        except Exception as e:
            print(f"Error parsing AI response: {e}")
            return SearchResponse()
```
## File: config.py
```python
"""
Configuration management for PAIPI.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""
    
    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        self.openrouter_api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_base_url: str = os.getenv(
            "OPENROUTER_BASE_URL", 
            "https://openrouter.ai/api/v1"
        )
        self.default_model: str = os.getenv(
            "OPENROUTER_MODEL", 
            "anthropic/claude-3.5-sonnet"
        )
        self.app_title: str = os.getenv("APP_TITLE", "PAIPI - AI-Powered PyPI Search")
        self.app_description: str = os.getenv(
            "APP_DESCRIPTION",
            "PyPI search powered by AI's knowledge of Python packages"
        )
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.debug: bool = os.getenv("DEBUG", "false").lower() == "true"
        
    def validate(self) -> None:
        """Validate required configuration."""
        if not self.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is required. "
                "Please set it to your OpenRouter API key."
            )


# Global configuration instance
config = Config()
```
## File: main.py
```python
"""
FastAPI application for PAIPI - AI-powered PyPI search.
"""

from typing import Optional, Dict, Any
import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from .models import SearchResponse
from .client import OpenRouterClient
from .config import config


# Create FastAPI app
app = FastAPI(
    title=config.app_title,
    description=config.app_description,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS MIDDLEWARE CONFIGURATION ---
# Define the origins that are allowed to make requests to this API.
# In development, this is your Angular app's URL.
origins = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allows specified origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)
# --- END CORS CONFIGURATION ---

# Initialize OpenRouter client
try:
    config.validate()
    ai_client = OpenRouterClient()
except ValueError as e:
    print(f"Configuration error: {e}")
    ai_client = None


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with basic information."""
    return {
        "message": "Welcome to PAIPI - AI-Powered PyPI Search",
        "description": "Search for Python packages using AI knowledge",
        "endpoints": [
            "GET /search?q=<query> - Search for packages",
            "GET /docs - Interactive API documentation", 
            "GET /health - Health check"
        ]
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "paipi",
        "version": "0.1.0",
        "ai_client_available": ai_client is not None
    }


@app.get("/search", response_model=SearchResponse)
async def search_packages(
    q: str = Query(..., description="Search query for Python packages"),
    size: Optional[int] = Query(20, description="Number of results to return", ge=1, le=100)
) -> SearchResponse:
    """
    Search for Python packages using AI knowledge.
    
    This endpoint mimics the PyPI search API but uses AI to generate results
    based on its knowledge of Python packages rather than querying a database.
    
    Args:
        q: Search query string
        size: Maximum number of results to return (1-100)
        
    Returns:
        SearchResponse with AI-generated package results in PyPI format
    """
    if not ai_client:
        raise HTTPException(
            status_code=503,
            detail="AI service is not available. Please check configuration."
        )
    
    if not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )
    
    try:
        # Use asyncio to make the synchronous OpenAI client work with FastAPI
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            lambda: ai_client.search_packages(q.strip(), size)
        )
        return result
        
    except Exception as e:
        print(f"Search error: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while searching for packages"
        )


@app.exception_handler(404)
async def not_found_handler(request, exc) -> JSONResponse:
    """Custom 404 handler."""
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Endpoint not found",
            "message": "Try /search?q=<query> to search for packages or /docs for API documentation"
        }
    )


def main() -> None:
    """Main entry point for running the server."""
    import uvicorn
    
    print(f"Starting PAIPI server on {config.host}:{config.port}")
    print(f"Debug mode: {config.debug}")
    print(f"API documentation: http://{config.host}:{config.port}/docs")
    
    uvicorn.run(
        "paipi.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="debug" if config.debug else "info"
    )


if __name__ == "__main__":
    main()
```
## File: models.py
```python
"""
Pydantic models for PyPI-shaped API responses with type hints.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ProjectInfo(BaseModel):
    """Basic project information."""
    name: str
    version: str
    description: Optional[str] = None


class ProjectUrls(BaseModel):
    """Project URLs."""
    homepage: Optional[str] = None
    repository: Optional[str] = None
    documentation: Optional[str] = None
    download: Optional[str] = None


class ProjectDetails(BaseModel):
    """Detailed project information."""
    author: Optional[str] = None
    author_email: Optional[str] = None
    maintainer: Optional[str] = None
    maintainer_email: Optional[str] = None
    license: Optional[str] = None
    keywords: Optional[str] = None
    classifiers: List[str] = Field(default_factory=list)
    requires_python: Optional[str] = None
    project_urls: Optional[ProjectUrls] = None
    summary: Optional[str] = None
    platform: Optional[str] = None


class PackageRelease(BaseModel):
    """Package release information."""
    version: str
    yanked: bool = False
    yanked_reason: Optional[str] = None
    upload_time: Optional[datetime] = None


class PackageFile(BaseModel):
    """Package file information."""
    filename: str
    url: str
    hashes: Dict[str, str] = Field(default_factory=dict)
    requires_python: Optional[str] = None
    yanked: bool = False
    yanked_reason: Optional[str] = None
    upload_time: Optional[datetime] = None
    size: Optional[int] = None
    packagetype: str = "sdist"  # sdist, bdist_wheel, etc.


class SearchResult(BaseModel):
    """Individual search result matching PyPI format."""
    name: str
    version: str
    description: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    author_email: Optional[str] = None
    maintainer: Optional[str] = None
    maintainer_email: Optional[str] = None
    home_page: Optional[str] = None
    package_url: Optional[str] = None
    release_url: Optional[str] = None
    docs_url: Optional[str] = None
    download_url: Optional[str] = None
    bugtrack_url: Optional[str] = None
    keywords: Optional[str] = None
    license: Optional[str] = None
    classifiers: List[str] = Field(default_factory=list)
    platform: Optional[str] = None
    requires_python: Optional[str] = None
    project_urls: Dict[str, str] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """PyPI search API response format."""
    info: Dict[str, Any] = Field(default_factory=dict)
    results: List[SearchResult] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```
