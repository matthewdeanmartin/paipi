"""
FastAPI application for PAIPI - AI-powered PyPI search.
"""

from typing import Optional, Dict, Any
import asyncio
import os
import time
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from .models import SearchResponse
from .client import OpenRouterClient
from .config import config
from .package_cache import package_cache, CACHE_DB_PATH


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


# --- STARTUP & SHUTDOWN EVENTS ---
@app.on_event("startup")
async def startup_event():
    """On startup, intelligently load and update the package cache."""
    loop = asyncio.get_event_loop()

    # This helper runs synchronous checks in a thread to not block the event loop
    def check_cache_status():
        if not CACHE_DB_PATH.exists():
            return "missing"
        if not package_cache.has_data():
            return "empty"

        # Check if cache is older than 24 hours (86400 seconds)
        file_mod_time = os.path.getmtime(CACHE_DB_PATH)
        if (time.time() - file_mod_time) > 86400:
            return "outdated"

        return "recent"

    status = await loop.run_in_executor(None, check_cache_status)

    if status == "recent":
        print("Package cache is recent and populated. Loading into memory.")
        await loop.run_in_executor(None, package_cache.load_into_memory)
    elif status == "outdated":
        print("Package cache is outdated. Loading stale data and triggering background update.")
        # Load the old data first for immediate availability
        await loop.run_in_executor(None, package_cache.load_into_memory)
        # Then start the background update without awaiting it
        loop.run_in_executor(None, package_cache.update_cache)
    elif status in ["missing", "empty"]:
        if status == "missing":
            print("Package cache database not found.")
        else:  # empty
            print("Package cache is empty.")
        print("Triggering background update to populate cache.")
        # Start the background update without awaiting it
        loop.run_in_executor(None, package_cache.update_cache)


@app.on_event("shutdown")
def shutdown_event():
    """Close database connection on shutdown."""
    package_cache.close()
    print("Cache database connection closed.")


# --- END STARTUP & SHUTDOWN EVENTS ---

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