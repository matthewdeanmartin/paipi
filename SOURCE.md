## Tree for paipi
```
├── cache_manager.py
├── client.py
├── config.py
├── main.py
├── models.py
└── package_cache.py
```

## File: cache_manager.py
```python
"""
Comprehensive cache manager for search results, READMEs, and packages.
"""

import hashlib
import json
import sqlite3
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .models import ReadmeRequest, SearchResponse


class CacheManager:
    """Manages caching for search results, READMEs, and packages."""

    def __init__(self, cache_dir: Path = Path("pypi_cache")) -> None:
        """Initialize cache manager with database and file storage."""
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)

        self.db_path = self.cache_dir / "cache.db"
        self.packages_dir = self.cache_dir / "packages"
        self.packages_dir.mkdir(exist_ok=True)

        self._connection: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the cache database with required tables."""
        try:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self._connection.cursor()

            # Table for search results cache
            cursor.execute(
                """
                           CREATE TABLE IF NOT EXISTS search_cache
                           (
                               query_key
                               TEXT
                               PRIMARY
                               KEY,
                               original_query
                               TEXT
                               NOT
                               NULL,
                               results_json
                               TEXT
                               NOT
                               NULL,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           """
            )

            # Table for README cache
            cursor.execute(
                """
                           CREATE TABLE IF NOT EXISTS readme_cache
                           (
                               request_hash
                               TEXT
                               PRIMARY
                               KEY,
                               package_name
                               TEXT
                               NOT
                               NULL,
                               markdown_content
                               TEXT
                               NOT
                               NULL,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           """
            )

            # Table for package cache
            cursor.execute(
                """
                           CREATE TABLE IF NOT EXISTS package_cache
                           (
                               package_name
                               TEXT
                               PRIMARY
                               KEY,
                               zip_path
                               TEXT
                               NOT
                               NULL,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           """
            )

            self._connection.commit()
            print(f"Cache database initialized at {self.db_path}")

        except sqlite3.Error as e:
            print(f"Database error during cache initialization: {e}")
            self._connection = None

    def _generate_query_key(self, query: str) -> str:
        """Generate a cache key from search query (lowercase, stripped, order preserved)."""
        normalized_query = query.lower().strip()
        return normalized_query

    def _generate_readme_hash(self, request: ReadmeRequest) -> str:
        """Generate a hash from README request for caching."""
        # Convert to dict and create deterministic hash
        request_dict = request.dict()
        request_str = json.dumps(request_dict, sort_keys=True)
        return hashlib.sha256(request_str.encode()).hexdigest()

    def _get_package_dir(self, package_name: str) -> Path:
        """Get the directory path for a specific package."""
        # Normalize package name for filesystem
        safe_name = package_name.lower().replace("_", "-")
        return self.packages_dir / safe_name

    # Search results caching

    def get_cached_search(self, query: str) -> Optional[SearchResponse]:
        """Get cached search results for a query."""
        if not self._connection:
            return None

        query_key = self._generate_query_key(query)

        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT results_json FROM search_cache WHERE query_key = ?",
                (query_key,),
            )
            result = cursor.fetchone()

            if result:
                results_data = json.loads(result[0])
                return SearchResponse(**results_data)

        except (sqlite3.Error, json.JSONDecodeError) as e:
            print(f"Error retrieving cached search results: {e}")

        return None

    def cache_search_results(self, query: str, response: SearchResponse) -> None:
        """Cache search results for a query."""
        if not self._connection:
            return

        query_key = self._generate_query_key(query)

        try:
            cursor = self._connection.cursor()
            results_json = response.json()

            cursor.execute(
                """
                INSERT OR REPLACE INTO search_cache 
                (query_key, original_query, results_json) 
                VALUES (?, ?, ?)
            """,
                (query_key, query, results_json),
            )

            self._connection.commit()
            print(f"Cached search results for query: {query}")

        except (sqlite3.Error, json.JSONEncodeError) as e:
            print(f"Error caching search results: {e}")

    def get_all_cached_searches(self) -> List[SearchResponse]:
        """Get all cached search results for empty/blank queries."""
        if not self._connection:
            return []

        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT results_json FROM search_cache ORDER BY created_at DESC"
            )
            results = cursor.fetchall()

            all_responses = []
            for result in results:
                try:
                    results_data = json.loads(result[0])
                    response = SearchResponse(**results_data)
                    all_responses.append(response)
                except json.JSONDecodeError as e:
                    print(f"Error parsing cached search result: {e}")
                    continue

            return all_responses

        except sqlite3.Error as e:
            print(f"Error retrieving all cached searches: {e}")
            return []

    # README caching

    def get_cached_readme(self, request: ReadmeRequest) -> Optional[str]:
        """Get cached README for a request."""
        if not self._connection:
            return None

        request_hash = self._generate_readme_hash(request)

        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT markdown_content FROM readme_cache WHERE request_hash = ?",
                (request_hash,),
            )
            result = cursor.fetchone()

            if result:
                return result[0]

        except sqlite3.Error as e:
            print(f"Error retrieving cached README: {e}")

        return None

    def cache_readme(self, request: ReadmeRequest, markdown_content: str) -> None:
        """Cache README markdown content and save to file."""
        if not self._connection:
            return

        request_hash = self._generate_readme_hash(request)
        package_name = request.name

        try:
            # Save to database
            cursor = self._connection.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO readme_cache 
                (request_hash, package_name, markdown_content) 
                VALUES (?, ?, ?)
            """,
                (request_hash, package_name, markdown_content),
            )

            self._connection.commit()

            # Save to file system
            package_dir = self._get_package_dir(package_name)
            package_dir.mkdir(exist_ok=True)

            readme_path = package_dir / "README.md"
            readme_path.write_text(markdown_content, encoding="utf-8")

            print(f"Cached README for package: {package_name}")

        except (sqlite3.Error, OSError) as e:
            print(f"Error caching README: {e}")

    # Package caching

    def get_cached_package(self, package_name: str) -> Optional[bytes]:
        """Get cached package ZIP bytes."""
        if not self._connection:
            return None

        try:
            cursor = self._connection.cursor()
            cursor.execute(
                "SELECT zip_path FROM package_cache WHERE package_name = ?",
                (package_name,),
            )
            result = cursor.fetchone()

            if result:
                zip_path = Path(result[0])
                if zip_path.exists():
                    return zip_path.read_bytes()
                else:
                    # Clean up stale database entry
                    cursor.execute(
                        "DELETE FROM package_cache WHERE package_name = ?",
                        (package_name,),
                    )
                    self._connection.commit()

        except sqlite3.Error as e:
            print(f"Error retrieving cached package: {e}")

        return None

    def cache_package(self, package_name: str, zip_bytes: bytes) -> None:
        """Cache package ZIP bytes to file and database."""
        if not self._connection:
            return

        try:
            # Save ZIP file
            package_dir = self._get_package_dir(package_name)
            package_dir.mkdir(exist_ok=True)

            zip_path = package_dir / f"{package_name}.zip"
            zip_path.write_bytes(zip_bytes)

            # Save to database
            cursor = self._connection.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO package_cache 
                (package_name, zip_path) 
                VALUES (?, ?)
            """,
                (package_name, str(zip_path)),
            )

            self._connection.commit()
            print(f"Cached package ZIP for: {package_name}")

        except (sqlite3.Error, OSError) as e:
            print(f"Error caching package: {e}")

    def generate_stub_package(
        self, package_name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Generate a stub package ZIP with basic structure."""
        if metadata is None:
            metadata = {}

        # Create ZIP in memory
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Create basic package structure
            safe_name = package_name.lower().replace("-", "_")

            # pyproject.toml
            pyproject_content = f"""[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{package_name}"
version = "{metadata.get('version', '0.1.0')}"
description = "{metadata.get('description', f'A Python package named {package_name}')}"
authors = [
    {{name = "{metadata.get('author', 'Unknown')}", email = "{metadata.get('author_email', 'unknown@example.com')}"}}
]
license = {{text = "{metadata.get('license', 'MIT')}"}}
requires-python = "{metadata.get('python_requires', '>=3.8')}"
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12"
]

[project.urls]
Homepage = "{metadata.get('homepage', f'https://github.com/user/{package_name}')}"
Repository = "{metadata.get('repository', f'https://github.com/user/{package_name}')}"
"""
            zipf.writestr("pyproject.toml", pyproject_content)

            # README.md
            readme_content = f"""# {package_name}

{metadata.get('description', f'A Python package named {package_name}')}

## Installation

```bash
pip install {package_name}
```

## Usage

```python
import {safe_name}

# Your code here
```

## License

{metadata.get('license', 'MIT')}
"""
            zipf.writestr("README.md", readme_content)

            # Package __init__.py
            init_content = f'''"""
{package_name} - {metadata.get('description', f'A Python package named {package_name}')}
"""

__version__ = "{metadata.get('version', '0.1.0')}"
__author__ = "{metadata.get('author', 'Unknown')}"
__email__ = "{metadata.get('author_email', 'unknown@example.com')}"

# Your package code here
def hello():
    """Say hello from {package_name}."""
    return f"Hello from {package_name}!"
'''
            zipf.writestr(f"{safe_name}/__init__.py", init_content)

            # MANIFEST.in
            manifest_content = """include README.md
include LICENSE
recursive-include src *
"""
            zipf.writestr("MANIFEST.in", manifest_content)

            # LICENSE (if not provided)
            if not metadata.get("license_text"):
                license_content = f"""MIT License

Copyright (c) 2024 {metadata.get('author', 'Unknown')}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
                zipf.writestr("LICENSE", license_content)
            else:
                zipf.writestr("LICENSE", metadata["license_text"])

        zip_bytes = zip_buffer.getvalue()
        zip_buffer.close()

        return zip_bytes

    def clear_cache(self, cache_type: Optional[str] = None) -> None:
        """Clear cache entries. If cache_type is None, clears all caches."""
        if not self._connection:
            return

        try:
            cursor = self._connection.cursor()

            if cache_type == "search" or cache_type is None:
                cursor.execute("DELETE FROM search_cache")

            if cache_type == "readme" or cache_type is None:
                cursor.execute("DELETE FROM readme_cache")

            if cache_type == "package" or cache_type is None:
                cursor.execute("DELETE FROM package_cache")

            self._connection.commit()
            print(f"Cleared {cache_type or 'all'} cache(s)")

        except sqlite3.Error as e:
            print(f"Error clearing cache: {e}")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        if not self._connection:
            return {"search": 0, "readme": 0, "package": 0}

        try:
            cursor = self._connection.cursor()

            cursor.execute("SELECT COUNT(*) FROM search_cache")
            search_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM readme_cache")
            readme_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM package_cache")
            package_count = cursor.fetchone()[0]

            return {
                "search": search_count,
                "readme": readme_count,
                "package": package_count,
            }

        except sqlite3.Error as e:
            print(f"Error getting cache stats: {e}")
            return {"search": 0, "readme": 0, "package": 0}

    def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


# Global cache manager instance
cache_manager = CacheManager()
```
## File: client.py
```python
"""
OpenRouter AI client for generating PyPI-style search results.
"""

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .config import config
from .models import ReadmeRequest, SearchResponse, SearchResult
from .package_cache import package_cache


class OpenRouterClient:
    """Client for interacting with OpenRouter AI service via OpenAI interface."""

    def __init__(
        self, api_key: Optional[str] = None, base_url: Optional[str] = None
    ) -> None:
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
                        "You should return realistic package information in the exact JSON format requested.",
                    },
                    {"role": "user", "content": prompt},
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
                    # Check if the package exists in our cache
                    result.package_exists = package_cache.package_exists(result.name)
                    results.append(result)
                except Exception as e:
                    print(f"Error parsing result item: {e}")
                    continue

            return SearchResponse(
                info={"query": query, "count": len(results)}, results=results
            )

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Content: {content}")
            return SearchResponse()
        except Exception as e:
            print(f"Error parsing AI response: {e}")
            return SearchResponse()

    # --- add inside OpenRouterClient in client.py ---

    def generate_readme(self, req: "ReadmeRequest") -> str:
        """
        Ask the LLM for a structured JSON README outline, then render to clean Markdown.

        Returns:
            Markdown string suitable for README.md (no JSON punctuation).
        """
        prompt = self._build_readme_prompt(req)

        try:
            response = self.client.chat.completions.create(
                model=config.default_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior Python maintainer. "
                            "Return ONLY valid minified JSON. No markdown fences, no commentary."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=4000,
            )

            content = response.choices[0].message.content or ""
            data = self._extract_json(content)
            return self._render_readme_markdown(data)

        except Exception as e:
            print(f"Error generating README via OpenRouter: {e}")
            # Graceful fallback
            return f"# {req.name}\n\n{req.summary or ''}\n\n> README generation failed. Please try again."

    # --- helpers ---

    def _build_readme_prompt(self, req: "ReadmeRequest") -> str:
        """Builds the README generation prompt with strict JSON schema instructions."""
        # minimal context → reduce hallucinated sections, still flexible
        return (
            "Draft a comprehensive README as JSON with these keys:\n"
            "{\n"
            '  "title": str,\n'
            '  "tagline": str,\n'
            '  "badges": [str],\n'
            '  "description": str,\n'
            '  "features": [str],\n'
            '  "installation": { "text": str, "code": str },\n'
            '  "usage": [ { "title": str, "code": str } ],\n'
            '  "configuration": [ { "name": str, "description": str } ],\n'
            '  "links": { "Homepage": str, "Repository": str, "Documentation": str },\n'
            '  "license": str,\n'
            '  "contributing": str,\n'
            '  "faq": [ { "q": str, "a": str } ]\n'
            "}\n\n"
            "Rules:\n"
            "- Return ONLY valid JSON (no code fences, no trailing commas, no comments).\n"
            "- Prefer concise, accurate, copy-pasteable code blocks in `installation.code` and each `usage[].code`.\n"
            "- Omit sections that cannot be populated, or use empty arrays/strings.\n"
            "- Keep badges short (e.g., shields.io). Do not include HTML.\n\n"
            f"Project metadata (authoritative): {json.dumps(req.dict(), ensure_ascii=False)}"
        )

    def _extract_json(self, content: str) -> Dict[str, Any]:
        """
        Extract JSON whether or not the model wrapped it in code fences.
        """
        s = content.strip()
        if s.startswith("```"):
            # tolerate ```json or ``` wrapping
            try:
                s = s.split("```", 1)[1]
                s = s.split("```", 1)[0]
            except Exception:
                pass
        return json.loads(s)

    def _render_readme_markdown(self, data: Dict[str, Any]) -> str:
        """
        Turn the LLM's JSON into tidy, human-friendly Markdown.
        """

        def sec(title: str) -> str:
            return f"\n## {title}\n"

        lines: List[str] = []
        title = data.get("title") or ""
        tagline = data.get("tagline") or ""

        if title:
            lines.append(f"# {title}")
        if tagline:
            lines.append(f"\n> {tagline}")

        # badges
        badges = data.get("badges") or []
        if badges:
            lines.append("")
            for b in badges:
                lines.append(b)

        # description
        desc = (data.get("description") or "").strip()
        if desc:
            lines.append(sec("Description"))
            lines.append(desc)

        # features
        feats = data.get("features") or []
        if feats:
            lines.append(sec("Features"))
            for f in feats:
                lines.append(f"- {f}")

        # installation
        install = data.get("installation") or {}
        if install.get("text") or install.get("code"):
            lines.append(sec("Installation"))
            if install.get("text"):
                lines.append(install["text"])
            if install.get("code"):
                lines.append("\n```bash")
                lines.append(install["code"].strip())
                lines.append("```")

        # usage
        usage = data.get("usage") or []
        if usage:
            lines.append(sec("Usage"))
            for u in usage:
                title = u.get("title")
                code = u.get("code")
                if title:
                    lines.append(f"**{title}**")
                if code:
                    lines.append("\n```python")
                    lines.append(code.strip())
                    lines.append("```")

        # configuration
        cfg = data.get("configuration") or []
        if cfg:
            lines.append(sec("Configuration"))
            for item in cfg:
                name = item.get("name")
                desc = item.get("description")
                if name:
                    lines.append(f"- **{name}** — {desc or ''}".rstrip())

        # links
        links = data.get("links") or {}
        if links:
            lines.append(sec("Links"))
            for k, v in links.items():
                if v:
                    lines.append(f"- [{k}]({v})")

        # contributing
        contrib = data.get("contributing") or ""
        if contrib.strip():
            lines.append(sec("Contributing"))
            lines.append(contrib.strip())

        # license
        license_ = data.get("license") or ""
        if license_.strip():
            lines.append(sec("License"))
            lines.append(license_.strip())

        # faq
        faq = data.get("faq") or []
        if faq:
            lines.append(sec("FAQ"))
            for qa in faq:
                q = qa.get("q")
                a = qa.get("a")
                if q:
                    lines.append(f"**Q:** {q}")
                    if a:
                        lines.append(f"**A:** {a}")
                    lines.append("")

        return "\n".join(lines).strip() + "\n"
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
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self.default_model: str = os.getenv(
            "OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"
        )
        self.app_title: str = os.getenv("APP_TITLE", "PAIPI - AI-Powered PyPI Search")
        self.app_description: str = os.getenv(
            "APP_DESCRIPTION",
            "PyPI search powered by AI's knowledge of Python packages",
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
```
## File: models.py
```python
"""
Pydantic models for PyPI-shaped API responses with type hints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    package_exists: bool = Field(
        False,
        description="Whether the package name exists on PyPI according to the local cache.",
    )


class SearchResponse(BaseModel):
    """PyPI search API response format."""

    info: Dict[str, Any] = Field(default_factory=dict)
    results: List[SearchResult] = Field(default_factory=list)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ReadmeRequest(BaseModel):
    """Input metadata to draft a README."""

    name: str = Field(..., description="Project/package name")
    summary: Optional[str] = Field(None, description="One-line summary / tagline")
    description: Optional[str] = Field(None, description="Longer description")
    license: Optional[str] = None
    repo_url: Optional[str] = None
    homepage: Optional[str] = None
    documentation_url: Optional[str] = None
    install_cmd: Optional[str] = Field(None, description="e.g., pip install yourpkg")
    python_requires: Optional[str] = None
    features: Optional[List[str]] = None
    usage_snippets: Optional[List[str]] = Field(
        default=None, description="Code examples as raw code strings"
    )
    extras: Optional[Dict[str, Any]] = Field(
        default=None, description="Any additional metadata you want to pass through"
    )


class ReadmeResponse(BaseModel):
    """Markdown payload for README.md as a raw string."""

    markdown: str


class PackageGenerateRequest(BaseModel):
    """Stub: payload that will be sent to LLM to generate a package."""

    readme_markdown: str
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Everything needed to assemble a package (name, version, pyproject, module skeleton, etc.)",
    )
```
## File: package_cache.py
```python
"""
Manages a local cache of PyPI package names for fast lookups.

This module downloads the complete list of packages from the PyPI Simple Index,
stores them in an SQLite database, and provides a fast, in-memory check
to verify if a package name is legitimate.
"""

import re
import sqlite3
from pathlib import Path
from typing import Set

import httpx

# --- Constants ---
CACHE_DB_PATH = Path("paipi_cache.db")
PYPI_SIMPLE_URL = "https://pypi.org/simple/"


class PackageCache:
    """A singleton class to manage the PyPI package name cache."""

    _instance = None
    _db_path: Path
    _connection: sqlite3.Connection | None = None
    _package_names: Set[str] | None = None

    def __new__(cls, db_path: Path = CACHE_DB_PATH):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db_path = db_path
            cls._instance._init_db()
        return cls._instance

    def _init_db(self) -> None:
        """Initialize the database and table if they don't exist."""
        try:
            # check_same_thread=False is safe for this read-heavy, single-writer use case
            self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
            cursor = self._connection.cursor()
            cursor.execute(
                """
                           CREATE TABLE IF NOT EXISTS packages
                           (
                               name
                               TEXT
                               PRIMARY
                               KEY
                           )
                           """
            )
            self._connection.commit()
            print(f"Cache database initialized at {self._db_path}")
        except sqlite3.Error as e:
            print(f"Database error during initialization: {e}")
            self._connection = None

    def load_into_memory(self):
        """Load all package names from DB into a set for fast lookups."""
        if self._package_names is not None:
            return  # Already loaded
        if self._connection:
            try:
                print("Loading package names from database into memory...")
                cursor = self._connection.cursor()
                cursor.execute("SELECT name FROM packages")
                self._package_names = {row[0] for row in cursor.fetchall()}
                print(
                    f"Loaded {len(self._package_names)} package names into memory cache."
                )
            except sqlite3.Error as e:
                print(f"Database error loading names into memory: {e}")
                self._package_names = set()
        else:
            self._package_names = set()

    def has_data(self) -> bool:
        """Check if the cache contains any package data."""
        if not self._connection:
            return False
        try:
            cursor = self._connection.cursor()
            # Use EXISTS for an efficient check without counting all rows
            cursor.execute("SELECT EXISTS(SELECT 1 FROM packages)")
            result = cursor.fetchone()
            return result[0] == 1 if result else False
        except sqlite3.Error as e:
            print(f"Database error checking for data: {e}")
            return False

    def update_cache(self) -> None:
        """Fetch all package names from PyPI and update the local SQLite cache."""
        if not self._connection:
            print("Cannot update cache: database connection not available.")
            return

        print("Starting PyPI package list update from server...")
        try:
            with httpx.Client() as client:
                response = client.get(PYPI_SIMPLE_URL, timeout=120.0)
                response.raise_for_status()

            # Regex to find package names in the href attributes of the simple index
            package_names = re.findall(r'<a href="/simple/([^/]+)/">', response.text)

            if not package_names:
                print("Could not find any package names. Aborting cache update.")
                return

            cursor = self._connection.cursor()

            # Use a transaction for much faster inserts
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute("DELETE FROM packages")  # Clear old data
            cursor.executemany(
                "INSERT OR IGNORE INTO packages (name) VALUES (?)",
                [(name,) for name in package_names],
            )
            cursor.execute("COMMIT")

            print(f"Successfully updated cache with {len(package_names)} packages.")
            self._package_names = None  # Force reload on next check
            self.load_into_memory()  # Refresh in-memory set

        except httpx.RequestError as e:
            print(f"HTTP error while fetching package list: {e}")
        except sqlite3.Error as e:
            print(f"Database error during cache update: {e}")
            if self._connection:
                self._connection.rollback()
        except Exception as e:
            print(f"An unexpected error occurred during cache update: {e}")

    def package_exists(self, package_name: str) -> bool:
        """Check if a package exists in the cache (case-insensitive and normalized)."""
        if self._package_names is None:
            self.load_into_memory()

        # PyPI names are normalized to be lowercase with hyphens instead of underscores.
        normalized_name = package_name.lower().replace("_", "-")

        return normalized_name in self._package_names if self._package_names else False

    def close(self):
        """Closes the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


# Global instance to be used across the application
package_cache = PackageCache()
```
