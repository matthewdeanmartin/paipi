"""
FastAPI application for PAIPI - AI-powered PyPI search.
"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
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
from .client_search import OpenRouterClientSearch, SearchGenerationError
from .config import _parse_models, config
from .models import (
    PackageGenerateRequest,
    ReadmeRequest,
    SearchResponse,
    SearchResult,
)
from .openrouter_models import resolve_model_pool
from .package_cache import CACHE_DB_PATH, package_cache
from .pypi_scraper import PypiScraper


class AvailabilityRequest(BaseModel):
    names: list[str]


class AvailabilityResponseItem(BaseModel):
    name: str
    package_cached: bool
    readme_cached: bool
    package_model: Optional[str] = None
    readme_model: Optional[str] = None


def _optional_model_headers(model_used: Optional[str]) -> Dict[str, str]:
    """Return response headers carrying model metadata when available."""
    if not model_used:
        return {}
    return {"X-PAIPI-Model-Used": model_used}


async def startup_event() -> None:
    """On startup, intelligently load and update the package cache."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _refresh_runtime_model_pool)

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


def shutdown_event() -> None:
    """Close database connections on shutdown."""
    package_cache.close()
    cache_manager.close()
    print("Cache database connections closed.")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Run startup and shutdown hooks using FastAPI's lifespan API."""
    await startup_event()
    try:
        yield
    finally:
        shutdown_event()


# Create FastAPI app
app = FastAPI(
    title=config.app_title,
    description=config.app_description,
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
api_router = APIRouter(prefix="/api")


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


# --- STATIC FILE SERVING (Angular SPA) ---
# The built Angular app lives at paipi-app/dist/paipi-app/browser relative to
# the repo root. When installed as a package the browser assets are copied into
# paipi/static, so we look for them relative to this file first and fall back
# to the repo layout.
_HERE = Path(__file__).parent
_STATIC_CANDIDATES = [
    _HERE / "static",  # installed package
    _HERE.parent / "paipi-app" / "dist" / "paipi-app" / "browser",  # repo dev
]
_STATIC_DIR: Optional[Path] = next((p for p in _STATIC_CANDIDATES if p.is_dir()), None)
_STATIC_FILES = StaticFiles(directory=str(_STATIC_DIR), html=True) if _STATIC_DIR else None


# --- END STATIC FILE SERVING ---

# Initialize OpenRouter clients
ai_client: Optional[OpenRouterClientSearch] = None
readme_client: Optional[OpenRouterClientReadMe] = None


def _configure_ai_clients() -> None:
    """Initialize or disable AI clients based on current configuration."""
    global ai_client, readme_client

    if not config.openrouter_api_key:
        ai_client = None
        readme_client = None
        return

    ai_client = OpenRouterClientSearch()
    readme_client = OpenRouterClientReadMe()


def _refresh_runtime_model_pool() -> None:
    """Refresh the runtime model pool from live OpenRouter availability."""
    if not config.openrouter_api_key:
        return

    resolution = resolve_model_pool(
        api_key=config.openrouter_api_key,
        base_url=config.openrouter_base_url,
        configured_models=config.configured_openrouter_models,
    )
    config.set_openrouter_models(resolution.selected_models)

    if resolution.unavailable_configured_models:
        print(
            "Skipping unavailable configured model(s): "
            + ", ".join(resolution.unavailable_configured_models)
        )

    print("Using OpenRouter model pool: " + ", ".join(config.openrouter_models))
    _configure_ai_clients()


_configure_ai_clients()

pypi_scraper = PypiScraper()


# --- CORE ENDPOINTS ---
@app.get("/api")
async def api_root() -> Dict[str, Any]:
    """API root endpoint with basic information."""
    return {
        "message": "Welcome to PAIPI - AI-Powered PyPI Search",
        "description": "Search for Python packages using AI knowledge",
        "endpoints": [
            "GET /api/search?q=<query> - Search for packages",
            "POST /api/readme - Generate README.md",
            "POST /api/generate_package - Generate package ZIP",
            "GET /api/cache/stats - Get cache statistics",
            "DELETE /api/cache/clear - Clear cache",
            "GET /api/docs - Interactive API documentation",
            "GET /api/health - Health check",
        ],
    }


@api_router.get("/health")
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


@api_router.get("/search", response_model=SearchResponse)
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
                readme_meta = await loop.run_in_executor(
                    None, lambda: cache_manager.get_readme_metadata_by_name(result.name)
                )
                package_meta = await loop.run_in_executor(
                    None, lambda: cache_manager.get_package_metadata_by_name(result.name)
                )
                result.readme_model = readme_meta.get("model")
                result.package_model = package_meta.get("model")
                result.package_cached = bool(package_meta)

        # 2. Augment all results concurrently
        if ai_response.results:
            tasks = [augment_result(res) for res in ai_response.results]
            await asyncio.gather(*tasks)

        # 3. Cache the augmented results
        await loop.run_in_executor(
            None, lambda: cache_manager.cache_search_results(query, ai_response)
        )
        return ai_response

    except SearchGenerationError as e:
        print(f"Search error: {e}")
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        print(f"Search error: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while searching for packages"
        ) from e


# --- add endpoints in main.py ---


@api_router.post(
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
            readme_meta = await loop.run_in_executor(
                None, lambda: cache_manager.get_readme_metadata_by_name(req.name)
            )
            return PlainTextResponse(
                content=cached_readme,
                media_type="text/markdown",
                headers=_optional_model_headers(readme_meta.get("model")),
            )

    except Exception as e:
        print(f"Error checking README cache: {e}")

    # Generate new README via AI
    try:
        loop = asyncio.get_event_loop()
        markdown, model_used = await loop.run_in_executor(
            None, lambda: readme_client.generate_readme_markdown_with_model(req)
        )

        # Cache the results
        await loop.run_in_executor(
            None, lambda: cache_manager.cache_readme(req, markdown, model_used)
        )

        # Return as raw markdown (not JSON) so clients can save directly as README.md
        return PlainTextResponse(
            content=markdown,
            media_type="text/markdown",
            headers=_optional_model_headers(model_used),
        )

    except Exception as e:
        print(f"README generation error: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while generating README"
        ) from e


@api_router.post(
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
            package_meta = await loop.run_in_executor(
                None, lambda: cache_manager.get_package_metadata_by_name(package_name)
            )
            # What was intended here?
            # from io import BytesIO
            # _zip_io = BytesIO(cached_zip)
            return StreamingResponse(
                iter([cached_zip]),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{package_name}.zip"',
                    **_optional_model_headers(package_meta.get("model")),
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
            None, lambda: cache_manager.cache_package(package_name, zip_bytes, normalized_model)
        )

        return StreamingResponse(
            iter([zip_bytes]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{package_name}.zip"',
                **_optional_model_headers(normalized_model),
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


@api_router.get("/cache/stats")
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


@api_router.delete("/cache/clear")
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


@api_router.get("/availability")
async def availability(
    name: str = Query(..., description="Package name")
) -> Dict[str, Any]:
    """Return whether README and package ZIP are already cached for a name."""
    loop = asyncio.get_event_loop()
    readme_cached, package_cached, readme_meta, package_meta = await asyncio.gather(
        loop.run_in_executor(None, lambda: cache_manager.has_readme_by_name(name)),
        loop.run_in_executor(None, lambda: cache_manager.has_package_by_name(name)),
        loop.run_in_executor(None, lambda: cache_manager.get_readme_metadata_by_name(name)),
        loop.run_in_executor(None, lambda: cache_manager.get_package_metadata_by_name(name)),
    )
    return {
        "name": name,
        "readme_cached": bool(readme_cached),
        "package_cached": bool(package_cached),
        "readme_model": readme_meta.get("model"),
        "package_model": package_meta.get("model"),
    }


@api_router.post("/availability/batch")
async def availability_batch(payload: AvailabilityRequest) -> Dict[str, Any]:
    """Batch availability check for multiple names."""
    loop = asyncio.get_event_loop()
    results: list[Dict[str, Any]] = []
    for n in payload.names:
        readme_cached, package_cached, readme_meta, package_meta = await asyncio.gather(
            loop.run_in_executor(
                None,
                lambda n=n: cache_manager.has_readme_by_name(n),  # type: ignore[misc]
            ),
            loop.run_in_executor(
                None,
                lambda n=n: cache_manager.has_package_by_name(n),  # type: ignore[misc]
            ),
            loop.run_in_executor(
                None,
                lambda n=n: cache_manager.get_readme_metadata_by_name(n),  # type: ignore[misc]
            ),
            loop.run_in_executor(
                None,
                lambda n=n: cache_manager.get_package_metadata_by_name(n),  # type: ignore[misc]
            ),
        )
        results.append(
            {
                "name": n,
                "readme_cached": bool(readme_cached),
                "package_cached": bool(package_cached),
                "readme_model": readme_meta.get("model"),
                "package_model": package_meta.get("model"),
            }
        )
    return {"items": results}


@api_router.get(
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
    md, readme_meta = await asyncio.gather(
        loop.run_in_executor(None, lambda: cache_manager.get_readme_by_name(name)),
        loop.run_in_executor(None, lambda: cache_manager.get_readme_metadata_by_name(name)),
    )
    if not md:
        raise HTTPException(status_code=404, detail="README not found for this package")
    return PlainTextResponse(
        content=md,
        media_type="text/markdown",
        headers=_optional_model_headers(readme_meta.get("model")),
    )


@api_router.get("/search/history")
async def search_history() -> Dict[str, Any]:
    """Return saved past searches with timestamps and result counts."""
    loop = asyncio.get_event_loop()
    hist = await loop.run_in_executor(None, cache_manager.get_search_history)
    return {"items": hist}


app.include_router(api_router)


def _get_spa_index() -> Path:
    """Return the bundled SPA entrypoint if available."""
    if not _STATIC_DIR:
        raise HTTPException(status_code=404, detail="UI not found")

    index = _STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="UI not found")

    return index


if _STATIC_FILES:

    @app.get("/", include_in_schema=False)
    async def serve_root() -> FileResponse:
        """Serve the SPA root page."""
        return FileResponse(str(_get_spa_index()))


    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve static SPA assets and fall back to index.html for client routes."""
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Endpoint not found")

        asset_path = (_STATIC_DIR / full_path).resolve()  # type: ignore[operator]
        try:
            asset_path.relative_to(_STATIC_DIR.resolve())  # type: ignore[union-attr]
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Static asset not found") from exc

        if asset_path.is_file():
            return FileResponse(str(asset_path))

        if Path(full_path).suffix:
            raise HTTPException(status_code=404, detail="Static asset not found")

        return FileResponse(str(_get_spa_index()))


@app.exception_handler(404)
async def not_found_handler(request: Request, _exc: Any) -> JSONResponse:
    """Custom 404 handler."""
    if not request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Page not found",
                "message": "Try / for the web UI or /api/docs for API documentation",
            },
        )

    return JSONResponse(
        status_code=404,
        content={
            "detail": "Endpoint not found",
            "message": "Try /api/search?q=<query> to search for packages or /api/docs for API documentation",
        },
    )


def _run_server() -> None:
    """Start the uvicorn server (shared by main() and start())."""
    import uvicorn

    host = config.host
    port = config.port
    print(f"Starting PAIPI server on {host}:{port}")
    print(f"Debug mode: {config.debug}")
    print(f"API documentation: http://localhost:{port}/api/docs")
    print(f"Cache directory: {cache_manager.cache_dir}")
    if _STATIC_DIR:
        print(f"Web UI: http://localhost:{port}/")
    else:
        print("Web UI: not found (run 'make ui-bundle' to build the UI)")

    uvicorn.run(
        "paipi.main:app",
        host=host,
        port=port,
        reload=config.debug,
        log_level="debug" if config.debug else "info",
    )


def main() -> None:
    """Entry point for `paipi` — starts the API server (no onboarding)."""
    _run_server()


def start() -> None:
    """
    Entry point for `paipi start` — runs first-run onboarding if needed,
    then starts the full server (API + bundled Angular UI).
    """
    from paipi.onboarding import ensure_api_key

    api_key = ensure_api_key()
    # Make the freshly-entered key available to the rest of the process
    # (config was already instantiated at import time, so patch it directly)
    if api_key and not config.openrouter_api_key:
        config.openrouter_api_key = api_key
        os.environ["OPENROUTER_API_KEY"] = api_key

    configured_models = _parse_models(os.environ.get("OPENROUTER_MODELS"))
    if not configured_models:
        configured_models = _parse_models(os.environ.get("OPENROUTER_MODEL"))
    if configured_models:
        config.configured_openrouter_models = configured_models
        config.set_openrouter_models(configured_models)

    _configure_ai_clients()
    _run_server()


if __name__ == "__main__":
    main()
