"""
FastAPI application for PAIPI - AI-powered PyPI search.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from paipi import __about__
from paipi.coder.generate_package import (
    DockerOpenInterpreter,
    GenerationConfig,
    LibrarySpec,
)
from paipi.main_package_glue import _normalize_model, _zip_dir_to_bytes

from .cache_manager import cache_manager
from .client_readme import OpenRouterClientReadMe
from .client_search import OpenRouterClientSearch
from .config import config
from .models import (
    PackageGenerateRequest,
    ReadmeRequest,
    SearchResponse,
    SearchResult,
)
from .package_cache import CACHE_DB_PATH, package_cache
from .pypi_scraper import PypiScraper


class AvailabilityRequest(BaseModel):
    names: list[str]


class AvailabilityResponseItem(BaseModel):
    name: str
    package_cached: bool
    readme_cached: bool


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
async def startup_event() -> None:
    """On startup, intelligently load and update the package cache."""
    loop = asyncio.get_event_loop()

    # This helper runs synchronous checks in a thread to not block the event loop
    def check_cache_status() -> str:
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
def shutdown_event() -> None:
    """Close database connections on shutdown."""
    package_cache.close()
    cache_manager.close()
    print("Cache database connections closed.")


# --- END STARTUP & SHUTDOWN EVENTS ---

# Initialize OpenRouter client
config.validate()
ai_client = OpenRouterClientSearch()
readme_client = OpenRouterClientReadMe()

pypi_scraper = PypiScraper()


# --- CORE ENDPOINTS ---
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
        "version": __about__.__version__,
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
    Search for Python packages using AI knowledge, augmented with live PyPI data.

    This endpoint uses AI to generate a list of relevant packages, then verifies
    each one against the official PyPI API. Real packages are updated with live
    metadata, while non-existent ones remain as AI suggestions. Results are cached.

    Args:
        q: Search query string.
        size: Maximum number of results to return (1-100).

    Returns:
        SearchResponse with AI-generated and PyPI-verified package results.
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
        # 1. Get initial results from the AI
        ai_response = await loop.run_in_executor(
            None, lambda: ai_client.search_packages(query, size or 20)
        )

        # --- MODIFICATION START: Add a Semaphore to limit concurrency ---
        semaphore = asyncio.Semaphore(10)

        # Helper to augment a single result with real PyPI data
        async def augment_result(result: SearchResult) -> None:
            async with semaphore:
                metadata = await pypi_scraper.get_project_metadata(result.name)
                if not (metadata and "info" in metadata):
                    result.package_exists = False
                    result.readme_cached = False
                    result.package_cached = False
                    return

                info = metadata["info"]
                result.version = info.get("version", "N/A")
                result.summary = info.get("summary")
                readme_content = info.get("description")
                result.description = readme_content
                result.author = info.get("author")
                result.home_page = info.get("home_page")
                result.license = info.get("license")
                result.requires_python = info.get("requires_python")
                result.package_url = info.get("package_url")
                result.project_urls = info.get("project_urls", {})

                if readme_content:
                    readme_req = ReadmeRequest(
                        name=result.name,
                        summary=result.summary,
                        description=result.description,
                        install_cmd="",
                    )
                    await loop.run_in_executor(
                        None,
                        lambda: cache_manager.cache_readme(readme_req, readme_content),
                    )
                    result.readme_cached = True
                else:
                    result.readme_cached = await loop.run_in_executor(
                        None, lambda: cache_manager.has_readme_by_name(result.name)
                    )

        # 2. Augment all results concurrently
        if ai_response.results:
            tasks = [augment_result(res) for res in ai_response.results]
            await asyncio.gather(*tasks)

        # 3. Cache the augmented results
        await loop.run_in_executor(
            None, lambda: cache_manager.cache_search_results(query, ai_response)
        )
        return ai_response

    except Exception as e:
        print(f"Search error: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while searching for packages"
        ) from e


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
            None, lambda: readme_client.generate_readme(req)
        )
        markdown = await loop.run_in_executor(
            None, lambda: readme_client.generate_readme_markdown(req)
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
        ) from e


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
    Generate a package ZIP from README + metadata using the Docker Open Interpreter
    flow in paipi.generate_package, with simple name-based caching.

    Request model: PackageGenerateRequest (readme_markdown + metadata). :contentReference[oaicite:1]{index=1}
    """
    # We still guard on ai_client presence if you use it as a feature-flag
    if not ai_client:
        raise HTTPException(
            status_code=503,
            detail="AI service is not available. Please check configuration.",
        )

    if not payload.readme_markdown:
        raise HTTPException(status_code=400, detail="readme_markdown is required")

    package_name = payload.metadata.get("name", "unknown-package")

    # 1) Cache check (same behavior you had)
    try:
        loop = asyncio.get_event_loop()
        cached_zip = await loop.run_in_executor(
            None, lambda: cache_manager.get_cached_package(package_name)
        )

        if cached_zip:
            # What was intended here?
            # from io import BytesIO
            # _zip_io = BytesIO(cached_zip)
            return StreamingResponse(
                iter([cached_zip]),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{package_name}.zip"'
                },
            )

    except Exception as e:
        print(f"Error checking package cache: {e}")

    # 2) Not cached → invoke generator
    try:
        # Pull options from metadata with safe fallbacks
        python_version = str(payload.metadata.get("python_version", "3.11"))
        model_requested = payload.metadata.get("model")
        normalized_model = _normalize_model(model_requested)

        # pypi_description is optional; fallback to summary/description/name
        pypi_description = (
            payload.metadata.get("pypi_description")
            or payload.metadata.get("summary")
            or payload.metadata.get("description")
            or f"Auto-generated library {package_name}"
        )

        # Additional requirements list (optional)
        additional_requirements = payload.metadata.get("additional_requirements") or []

        # Build the generator config
        gen_config = GenerationConfig(
            python_version=python_version,
            cache_folder=str(Path("pypi_cache") / "generated_libs"),
            timeout_seconds=int(payload.metadata.get("timeout_seconds", 3600)),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            model=normalized_model,
            # you can expose container_name/max_retries via metadata if desired
        )

        generator = DockerOpenInterpreter(gen_config)

        spec = LibrarySpec(
            name=package_name,
            python_version=python_version,
            pypi_description=pypi_description,
            readme_content=payload.readme_markdown,
            additional_requirements=additional_requirements,
        )

        # Run the container & get an output directory path
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: generator.generate_library(spec)
        )

        output_dir = Path(result["output_directory"])

        # 3) Zip the output directory in-memory
        zip_bytes = await loop.run_in_executor(
            None, lambda: _zip_dir_to_bytes(output_dir)
        )

        # 4) Cache the bytes by package name (same key you were using)
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

    except HTTPException:
        # bubble up explicit HTTP errors
        raise
    except Exception as e:
        print(f"Package generation error: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while generating package"
        ) from e


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


@app.get("/availability")
async def availability(
    name: str = Query(..., description="Package name")
) -> Dict[str, Any]:
    """Return whether README and package ZIP are already cached for a name."""
    loop = asyncio.get_event_loop()
    readme_cached, package_cached = await asyncio.gather(
        loop.run_in_executor(None, lambda: cache_manager.has_readme_by_name(name)),
        loop.run_in_executor(None, lambda: cache_manager.has_package_by_name(name)),
    )
    return {
        "name": name,
        "readme_cached": bool(readme_cached),
        "package_cached": bool(package_cached),
    }


@app.post("/availability/batch")
async def availability_batch(payload: AvailabilityRequest) -> Dict[str, Any]:
    """Batch availability check for multiple names."""
    loop = asyncio.get_event_loop()
    results: list[Dict[str, Any]] = []
    for n in payload.names:
        readme_cached, package_cached = await asyncio.gather(
            loop.run_in_executor(
                None,
                lambda n=n: cache_manager.has_readme_by_name(n),  # type: ignore[misc]
            ),
            loop.run_in_executor(
                None,
                lambda n=n: cache_manager.has_package_by_name(n),  # type: ignore[misc]
            ),
        )
        results.append(
            {
                "name": n,
                "readme_cached": bool(readme_cached),
                "package_cached": bool(package_cached),
            }
        )
    return {"items": results}


@app.get(
    "/readme/by-name/{name}",
    response_class=PlainTextResponse,
    responses={
        200: {"content": {"text/markdown": {}}},
        404: {"description": "Not found"},
    },
)
async def get_readme_by_name(name: str) -> PlainTextResponse:
    """Return the most recent cached README for a package name, if present."""
    loop = asyncio.get_event_loop()
    md = await loop.run_in_executor(
        None, lambda: cache_manager.get_readme_by_name(name)
    )
    if not md:
        raise HTTPException(status_code=404, detail="README not found for this package")
    return PlainTextResponse(content=md, media_type="text/markdown")


@app.get("/search/history")
async def search_history() -> Dict[str, Any]:
    """Return saved past searches with timestamps and result counts."""
    loop = asyncio.get_event_loop()
    hist = await loop.run_in_executor(None, cache_manager.get_search_history)
    return {"items": hist}


@app.exception_handler(404)
async def not_found_handler(_request: Any, _exc: Any) -> JSONResponse:
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
