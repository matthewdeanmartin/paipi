"""
FastAPI application for PAIPI - AI-powered PyPI search.
"""

import asyncio
import os
import time
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware

from .cache_manager import cache_manager
from .client import OpenRouterClient
from .config import config
from .models import (
    PackageGenerateRequest,
    ReadmeRequest,
    ReadmeResponse,
    SearchResponse,
)
from .package_cache import CACHE_DB_PATH, package_cache

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
        print(
            "Package cache is outdated. Loading stale data and triggering background update."
        )
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

    # Print cache manager stats
    stats = cache_manager.get_cache_stats()
    print(
        f"Cache stats - Search: {stats['search']}, README: {stats['readme']}, Package: {stats['package']}"
    )


@app.on_event("shutdown")
def shutdown_event():
    """Close database connections on shutdown."""
    package_cache.close()
    cache_manager.close()
    print("Cache database connections closed.")


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
            "POST /readme - Generate README.md",
            "POST /generate_package - Generate package ZIP",
            "GET /cache/stats - Get cache statistics",
            "DELETE /cache/clear - Clear cache",
            "GET /docs - Interactive API documentation",
            "GET /health - Health check",
        ],
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    cache_stats = cache_manager.get_cache_stats()
    return {
        "status": "healthy",
        "service": "paipi",
        "version": "0.1.0",
        "ai_client_available": ai_client is not None,
        "cache_stats": cache_stats,
    }


@app.get("/search", response_model=SearchResponse)
async def search_packages(
    q: str = Query(
        "",
        description="Search query for Python packages (empty for all cached results)",
    ),
    size: Optional[int] = Query(
        20, description="Number of results to return", ge=1, le=100
    ),
) -> SearchResponse:
    """
    Search for Python packages using AI knowledge with caching.

    This endpoint mimics the PyPI search API but uses AI to generate results
    based on its knowledge of Python packages. Results are cached for faster
    subsequent requests.

    Args:
        q: Search query string (empty string returns all cached results)
        size: Maximum number of results to return (1-100)

    Returns:
        SearchResponse with AI-generated package results in PyPI format
    """
    if not ai_client:
        raise HTTPException(
            status_code=503,
            detail="AI service is not available. Please check configuration.",
        )

    query = q.strip()

    # Handle empty query - return concatenated cached results
    if not query:
        try:
            # Use asyncio to make the synchronous OpenAI client work with FastAPI
            loop = asyncio.get_event_loop()
            all_cached = await loop.run_in_executor(
                None, cache_manager.get_all_cached_searches
            )

            # Combine all cached results
            all_results = []
            for response in all_cached:
                all_results.extend(response.results)

            # Limit to requested size
            limited_results = all_results[:size]

            return SearchResponse(
                info={"query": "", "count": len(limited_results)},
                results=limited_results,
            )

        except Exception as e:
            print(f"Error retrieving cached results: {e}")
            return SearchResponse(info={"query": "", "count": 0}, results=[])

    # Check cache first
    try:
        loop = asyncio.get_event_loop()
        cached_result = await loop.run_in_executor(
            None, lambda: cache_manager.get_cached_search(query)
        )

        if cached_result:
            # Limit cached results to requested size
            limited_results = cached_result.results[:size]
            return SearchResponse(info=cached_result.info, results=limited_results)

    except Exception as e:
        print(f"Error checking search cache: {e}")

    # Generate new results via AI
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: ai_client.search_packages(query, size)
        )

        # Cache the results
        await loop.run_in_executor(
            None, lambda: cache_manager.cache_search_results(query, result)
        )

        return result

    except Exception as e:
        print(f"Search error: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while searching for packages"
        )


# --- add endpoints in main.py ---


@app.post(
    "/readme",
    response_class=PlainTextResponse,
    responses={
        200: {"content": {"text/markdown": {}}},
        503: {"description": "AI service unavailable"},
        400: {"description": "Invalid request"},
    },
    summary="Generate README.md markdown with caching",
)
async def generate_readme(req: ReadmeRequest = Body(...)) -> PlainTextResponse:
    """
    Generate a README.md in **Markdown** using the AI client with caching.

    Subsequent requests with the same metadata will return cached results.
    """
    if not ai_client:
        raise HTTPException(
            status_code=503,
            detail="AI service is not available. Please check configuration.",
        )

    # Check cache first
    try:
        loop = asyncio.get_event_loop()
        cached_readme = await loop.run_in_executor(
            None, lambda: cache_manager.get_cached_readme(req)
        )

        if cached_readme:
            return PlainTextResponse(content=cached_readme, media_type="text/markdown")

    except Exception as e:
        print(f"Error checking README cache: {e}")

    # Generate new README via AI
    try:
        loop = asyncio.get_event_loop()
        markdown = await loop.run_in_executor(
            None, lambda: ai_client.generate_readme(req)
        )

        # Cache the results
        await loop.run_in_executor(
            None, lambda: cache_manager.cache_readme(req, markdown)
        )

        # Return as raw markdown (not JSON) so clients can save directly as README.md
        return PlainTextResponse(content=markdown, media_type="text/markdown")

    except Exception as e:
        print(f"README generation error: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while generating README"
        )


@app.post(
    "/generate_package",
    responses={
        200: {"content": {"application/zip": {}}},
        503: {"description": "AI service unavailable"},
        400: {"description": "Invalid request"},
    },
    summary="Generate a package ZIP with caching",
)
async def generate_package(
    payload: PackageGenerateRequest = Body(...),
) -> StreamingResponse:
    """
    Generate a package ZIP from README + metadata with caching.

    For now, this generates a stub package with basic structure.
    Future versions will use AI to generate more sophisticated packages.
    """
    if not ai_client:
        raise HTTPException(
            status_code=503,
            detail="AI service is not available. Please check configuration.",
        )

    package_name = payload.metadata.get("name", "unknown-package")

    # Check cache first
    try:
        loop = asyncio.get_event_loop()
        cached_zip = await loop.run_in_executor(
            None, lambda: cache_manager.get_cached_package(package_name)
        )

        if cached_zip:
            from io import BytesIO

            zip_io = BytesIO(cached_zip)
            return StreamingResponse(
                iter([cached_zip]),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{package_name}.zip"'
                },
            )

    except Exception as e:
        print(f"Error checking package cache: {e}")

    # Generate new package
    try:
        loop = asyncio.get_event_loop()
        zip_bytes = await loop.run_in_executor(
            None,
            lambda: cache_manager.generate_stub_package(package_name, payload.metadata),
        )

        # Cache the package
        await loop.run_in_executor(
            None, lambda: cache_manager.cache_package(package_name, zip_bytes)
        )

        return StreamingResponse(
            iter([zip_bytes]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{package_name}.zip"'
            },
        )

    except Exception as e:
        print(f"Package generation error: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while generating package"
        )


@app.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    try:
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(None, cache_manager.get_cache_stats)
        return {
            "status": "success",
            "cache_stats": stats,
            "cache_directory": str(cache_manager.cache_dir),
        }
    except Exception as e:
        print(f"Error getting cache stats: {e}")
        return {
            "status": "error",
            "error": str(e),
            "cache_stats": {"search": 0, "readme": 0, "package": 0},
        }


@app.delete("/cache/clear")
async def clear_cache(
    cache_type: Optional[str] = Query(
        None,
        description="Type of cache to clear: 'search', 'readme', 'package', or None for all",
    )
) -> Dict[str, str]:
    """Clear cache entries."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: cache_manager.clear_cache(cache_type))

        message = f"Cleared {cache_type or 'all'} cache(s) successfully"
        return {"status": "success", "message": message}

    except Exception as e:
        print(f"Error clearing cache: {e}")
        return {"status": "error", "message": str(e)}


@app.exception_handler(404)
async def not_found_handler(request, exc) -> JSONResponse:
    """Custom 404 handler."""
    return JSONResponse(
        status_code=404,
        content={
            "detail": "Endpoint not found",
            "message": "Try /search?q=<query> to search for packages or /docs for API documentation",
        },
    )


def main() -> None:
    """Main entry point for running the server."""
    import uvicorn

    print(f"Starting PAIPI server on {config.host}:{config.port}")
    print(f"Debug mode: {config.debug}")
    print(f"API documentation: http://{config.host}:{config.port}/docs")
    print(f"Cache directory: {cache_manager.cache_dir}")

    uvicorn.run(
        "paipi.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="debug" if config.debug else "info",
    )


if __name__ == "__main__":
    main()
