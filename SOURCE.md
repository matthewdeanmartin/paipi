## Tree for paipi
```
├── cache_manager.py
├── client_base.py
├── client_readme.py
├── client_search.py
├── config.py
├── generate_package.py
├── logger.py
├── main.py
├── main_package_glue.py
├── models.py
├── package_cache.py
├── py.typed
├── pypi_scraper.py
└── __about__.py
```

## File: cache_manager.py
```python
"""
Comprehensive cache manager for search results, READMEs, and packages.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

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

        except (sqlite3.Error, json.JSONDecodeError) as e:
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
                return cast(Optional[str], result[0])

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

    # Convenience lookups by package name (no request hash required)
    def has_readme_by_name(self, package_name: str) -> bool:
        """Return True if we have a cached README for this package name."""
        if not self._connection:
            return False
        try:
            c = self._connection.cursor()
            c.execute(
                "SELECT 1 FROM readme_cache WHERE package_name = ? LIMIT 1",
                (package_name,),
            )
            return c.fetchone() is not None
        except sqlite3.Error as e:
            print(f"Error checking README by name: {e}")
            return False

    def get_readme_by_name(self, package_name: str) -> Optional[str]:
        """Return the most recent README markdown by package name, if present."""
        if not self._connection:
            return None
        try:
            c = self._connection.cursor()
            # newest by created_at in case multiple entries exist
            c.execute(
                """
                SELECT markdown_content
                FROM readme_cache
                WHERE package_name = ?
                ORDER BY datetime(created_at) DESC LIMIT 1
                """,
                (package_name,),
            )
            row = c.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            print(f"Error fetching README by name: {e}")
            return None

    def list_readme_packages(self) -> List[Dict[str, Any]]:
        """Return list of packages for which we have cached READMEs."""
        if not self._connection:
            return []
        try:
            c = self._connection.cursor()
            c.execute(
                """
                SELECT package_name, MAX(datetime(created_at)) as latest
                FROM readme_cache
                GROUP BY package_name
                ORDER BY latest DESC
                """
            )
            rows = c.fetchall()
            return [{"package_name": r[0], "latest": r[1]} for r in rows]
        except sqlite3.Error as e:
            print(f"Error listing README packages: {e}")
            return []

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
                # Clean up stale database entry
                cursor.execute(
                    "DELETE FROM package_cache WHERE package_name = ?",
                    (package_name,),
                )
                self._connection.commit()

        except sqlite3.Error as e:
            print(f"Error retrieving cached package: {e}")

        return None

    def has_package_by_name(self, package_name: str) -> bool:
        """True if a package ZIP is cached (and file exists)."""
        if not self._connection:
            return False
        try:
            c = self._connection.cursor()
            c.execute(
                "SELECT zip_path FROM package_cache WHERE package_name = ?",
                (package_name,),
            )
            row = c.fetchone()
            if not row:
                return False
            return Path(row[0]).exists()
        except sqlite3.Error as e:
            print(f"Error checking package by name: {e}")
            return False

    # --- Search history ---
    def get_search_history(self) -> List[Dict[str, Any]]:
        """Return list of prior searches with created_at and lightweight counts."""
        if not self._connection:
            return []
        try:
            c = self._connection.cursor()
            c.execute(
                """
                SELECT original_query, results_json, created_at
                FROM search_cache
                ORDER BY datetime(created_at) DESC
                """
            )
            rows = c.fetchall()
            out: List[Dict[str, Any]] = []
            for q, res_json, ts in rows:
                count = 0
                try:
                    data = json.loads(res_json)
                    count = len(data.get("results", []))
                except json.JSONDecodeError:
                    pass
                out.append({"query": q, "count": count, "created_at": ts})
            return out
        except sqlite3.Error as e:
            print(f"Error retrieving search history: {e}")
            return []

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
## File: client_base.py
```python
"""
Base OpenRouter AI client.

Handles structured formats and simple retry workflows.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, cast

import untruncate_json
from openai import OpenAI

from .config import config
from .logger import llm_logger  # <--- IMPORT THE NEW LOGGER


class OpenRouterClientBase:
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

    # -----------------
    # Robust JSON repair helpers (used by search + legacy README path)
    # -----------------
    def ask_llm_to_fix_json(self, broken_json: str) -> Optional[str]:
        """Makes a one-shot request to the LLM to fix a broken JSON string."""
        print("--- Attempting one-shot LLM call to fix JSON ---")
        try:
            response = self.client.chat.completions.create(
                model=config.default_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a JSON repair utility. The user will provide a malformed JSON string. "
                        "Your sole task is to correct any syntax errors (e.g., trailing commas, "
                        "missing brackets, incorrect quoting) and return only the valid, minified JSON object. "
                        "Do not add any commentary, explanations, or markdown fences.",
                    },
                    {"role": "user", "content": broken_json},
                ],
                temperature=0.0,  # Be deterministic
                max_tokens=4000,
            )
            fixed_content = response.choices[0].message.content
            llm_logger.debug(
                f"LLM attempt to fix JSON resulted in:\n---\n{fixed_content}\n---"
            )
            return fixed_content
        except Exception as e:
            print(f"Error during LLM JSON fix attempt: {e}")
            llm_logger.error(f"Error during LLM JSON fix attempt: {e}")
            return None

    def parse_and_repair_json(self, content: str) -> Dict[str, Any]:
        """
        A robust method to parse JSON, with multiple repair strategies.

        Raises:
            ValueError: If all parsing and repair attempts fail.
        """
        # 1. Clean up common markdown fences
        s = content.strip()
        if s.startswith("```json"):
            s = s.split("```json", 1)[1]
            if "```" in s:
                s = s.rsplit("```", 1)[0]
        elif s.startswith("```"):
            s = s.split("```", 1)[1]
            if "```" in s:
                s = s.rsplit("```", 1)[0]

        s = s.strip()

        # 2. First attempt: Standard JSON load
        try:
            return cast(dict[str, Any], json.loads(s))
        except json.JSONDecodeError as e:
            print(f"Initial JSON decode failed: {e}. Attempting repairs...")
            llm_logger.warning(f"Initial JSON decode failed: {e}. Raw content:\n{s}")

        # 3. Second attempt: Use untruncate_json for common truncation issues
        try:
            repaired_s = untruncate_json.complete(s)
            data = json.loads(repaired_s)
            print("Successfully repaired JSON with `untruncate_json`.")
            llm_logger.info("Successfully repaired JSON with `untruncate_json`.")
            return cast(dict[str, Any], data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"`untruncate_json` failed: {e}. Attempting LLM-based fix.")
            llm_logger.warning(f"`untruncate_json` failed: {e}.")

        # 4. Third attempt: One-shot call to the LLM to fix the JSON
        fixed_json_str = self.ask_llm_to_fix_json(s)
        if fixed_json_str:
            try:
                data = json.loads(fixed_json_str)
                print("Successfully repaired JSON with a one-shot LLM call.")
                llm_logger.info("Successfully repaired JSON with a one-shot LLM call.")
                return cast(dict[str, Any], data)
            except json.JSONDecodeError as e:
                print(f"LLM-repaired JSON is still invalid: {e}")
                llm_logger.error(
                    f"LLM-repaired JSON is still invalid: {e}\nRepaired content:\n{fixed_json_str}"
                )

        # 5. If all else fails, raise an error.
        raise ValueError("All attempts to parse and repair the JSON response failed.")

    # --- END: NEW HELPER METHODS ---

    def extract_json(self, content: str) -> Dict[str, Any]:
        """
        Extract JSON whether or not the model wrapped it in code fences.
        (Legacy helper used by JSON-based README path.)
        """
        s = content.strip()
        if s.startswith("```"):
            # tolerate ```json or ``` wrapping
            try:
                s = s.split("```", 1)[1]
                s = s.split("```", 1)[0]
            except Exception:
                pass
        return cast(dict[str, Any], json.loads(s))
```
## File: client_readme.py
```python
"""
OpenRouter AI client for generating PyPI-style search results and READMEs.

- Keeps existing JSON-based README generator for backward compatibility.
- Adds a new Markdown-first README generator + new FastAPI endpoint sketch.
"""

from __future__ import annotations

import json
import random
from typing import Any, List, Optional

from openai import OpenAI

from .client_base import OpenRouterClientBase
from .config import config
from .logger import llm_logger  # <--- IMPORT THE NEW LOGGER
from .models import ReadmeRequest


class OpenRouterClientReadMe:
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
        self.base = OpenRouterClientBase(api_key, base_url)

    # -----------------
    # README (OLD JSON-BASED) — retained for backward compatibility
    # -----------------
    def generate_readme(self, req: ReadmeRequest) -> str:
        """
        OLD WAY: Ask the LLM for a structured JSON README outline, then render to Markdown.
        Kept for backward compatibility with existing callers.

        Returns:
            Markdown string suitable for README.md
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
            data = self.base.extract_json(content)
            return self._render_readme_markdown(data)

        except Exception as e:
            print(f"Error generating README via OpenRouter: {e}")
            llm_logger.error(
                f"Error generating README via OpenRouter for '{req.name}': {e}"
            )
            # Graceful fallback
            return f"# {req.name}\n\n{req.summary or ''}\n\n> README generation failed. Please try again."

    def _build_readme_prompt(self, req: ReadmeRequest) -> str:
        """Builds the JSON-based README generation prompt (legacy)."""
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

    # -----------------
    # README (NEW MARKDOWN-FIRST)
    # -----------------
    def generate_readme_markdown(self, req: ReadmeRequest) -> str:
        """
        NEW WAY: Ask the LLM to directly produce clean Markdown (no JSON),
        showing project metadata in a human-readable Markdown block.

        Hard rule: The model must **never** tell users to install with `pip install <package>`
        because PyPI already shows that at the top of the project page.
        """
        prompt = self._build_readme_md_prompt(req)

        try:
            response = self.client.chat.completions.create(
                model=config.default_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior Python maintainer and technical writer. "
                            "Return ONLY a complete, well-structured Markdown README. No JSON, no YAML, no HTML wrappers, no code fences around the entire document."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=4000,
            )

            content = response.choices[0].message.content or ""
            llm_logger.debug(
                f"[generate_readme_markdown for {req.name}] RAW LLM RESPONSE:\n---\n{content[:2000]}\n---"
            )
            # Best-effort light cleanup: strip stray outer fences if model adds them
            s = content.strip()
            if s.startswith("```") and s.endswith("```"):
                try:
                    s = s.split("\n", 1)[1]
                    s = s.rsplit("```", 1)[0]
                except Exception:
                    pass
            return s.strip() + ("\n" if not s.endswith("\n") else "")

        except Exception as e:
            print(f"Error generating README (markdown) via OpenRouter: {e}")
            llm_logger.error(
                f"Error generating README (markdown) via OpenRouter for '{req.name}': {e}"
            )
            return f"# {req.name}\n\n{req.summary or ''}\n\n> README generation failed. Please try again."

    def _build_readme_md_prompt(self, req: ReadmeRequest) -> str:
        """Create a Markdown-first README prompt with randomized, varied guidance."""
        meta = req.dict()

        # Present metadata as Markdown (not JSON)
        meta_md: List[str] = [
            f"**Name:** {meta.get('name','')}",
            f"**Summary:** {meta.get('summary','')}",
            f"**Description:** {meta.get('description','')}",
            f"**Homepage:** {meta.get('homepage','')}",
            f"**Repository:** {meta.get('repository','')}",
            f"**Documentation:** {meta.get('documentation','')}",
            f"**Keywords:** {', '.join(meta.get('keywords', []) or [])}",
            f"**License:** {meta.get('license','')}",
            f"**Requires Python:** {meta.get('requires_python','')}",
        ]
        meta_block = "\n".join(["### Project Metadata", "", *meta_md])

        # Instruction pool (we'll sample 6–12 each time to avoid repetition)
        instruction_pool = [
            "Start with an H1 title and an optional one-line tagline.",
            "Use short, descriptive badges if appropriate (e.g., shields.io).",
            "Provide a clear project description focusing on real capabilities.",
            "List key features in bullet points.",
            "Add a quickstart section that shows an immediate, minimal example.",
            "Include usage examples with copy-pasteable code blocks.",
            "Document configuration options succinctly in bullets or a simple table.",
            "Explain how to run tests and where to file issues.",
            "Keep sections concise and scannable; avoid marketing fluff.",
            "Use fenced code blocks for commands and Python snippets only.",
            "Include links (Homepage, Repository, Documentation) in a dedicated section.",
            "Close with License and Contributing notes.",
            "Avoid suggesting `pip install <package>`; PyPI already shows that prominently.",
            "Prefer practical examples over long prose; assume intermediate Python users.",
        ]
        k = random.randint(6, 12)
        sampled_instructions = random.sample(instruction_pool, k)

        # Pinned rules — always included
        pinned_rules = [
            "Return ONLY a Markdown document (no JSON/YAML wrappers).",
            "Do NOT say `pip install <package>` anywhere in the document.",
            "Avoid telling users to `pip install` in any form; assume PyPI page covers installation.",
            "Keep code blocks minimal and runnable.",
        ]

        bullet_lines = "\n".join([f"- {line}" for line in sampled_instructions])
        pinned_lines = "\n".join([f"- {line}" for line in pinned_rules])

        prompt = (
            f"Create a high-quality README.md in **pure Markdown** for the project below.\n\n"
            f"{meta_block}\n\n"
            "Follow these guidelines (varied each time):\n"
            f"{bullet_lines}\n\n"
            "Always enforce these rules:\n"
            f"{pinned_lines}\n\n"
            "Return only the README content."
        )
        return prompt

    def _render_readme_markdown(self, data: dict[str, Any]) -> str:
        """
        Turn the LLM's JSON into tidy, human-friendly Markdown. (Legacy path)
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
## File: client_search.py
```python
"""
OpenRouter AI client for generating PyPI-style search results and READMEs.

This version implements a new workflow:
1.  Iteratively asks the LLM for a plain-text list of relevant package names.
2.  Filters and validates the generated names.
3.  Checks for the actual existence of each package against a cache.
4.  Separates packages into 'real' and 'fake' lists.
5.  For 'fake' packages, makes a separate LLM call in batches to generate realistic metadata.
6.  For 'real' packages, it returns them to be handled by a PyPI scraper, preserving the original relevance-based order.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from openai import OpenAI

from .cache_manager import cache_manager
from .client_base import OpenRouterClientBase
from .config import config
from .logger import llm_logger
from .models import SearchResponse, SearchResult
from .package_cache import package_cache


class OpenRouterClientSearch:
    """
    Client for interacting with OpenRouter AI service via OpenAI interface.
    Implements a multi-step process to generate and validate package search results.
    """

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
        self.base = OpenRouterClientBase(api_key, base_url)

    def _generate_package_name_candidates(
        self, query: str, limit: int, max_iterations: int = 5
    ) -> List[str]:
        """
        Iteratively asks the LLM to generate a list of relevant package names.

        Args:
            query: The user's search query.
            limit: The target number of package names to generate.
            max_iterations: A safeguard to prevent infinite loops.

        Returns:
            A list of unique, cleaned package name strings.
        """
        found_packages: set[str] = set()
        iteration = 0
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant expert in Python packages. "
                    "Your task is to suggest relevant PyPI package names based on a query. "
                    "Return only a plain text list, with one package name per line."
                ),
            },
        ]

        while len(found_packages) < limit and iteration < max_iterations:
            iteration += 1
            num_needed = limit - len(found_packages)

            prompt = f'Based on the query "{query}", suggest {num_needed} relevant Python package names.'
            if found_packages:
                prompt += (
                    "\n\nAvoid suggesting the following packages that have already been found: "
                    f'{", ".join(sorted(list(found_packages)))}'
                )
            prompt += "\n\nReturn only the package names, one per line."

            # Update the last user message or add a new one
            if messages[-1]["role"] == "user":
                messages[-1]["content"] = prompt
            else:
                messages.append({"role": "user", "content": prompt})

            try:
                llm_logger.debug(
                    f"Name Generation Iteration {iteration}: Requesting {num_needed} packages."
                )
                response = self.client.chat.completions.create(
                    model=config.default_model,
                    messages=messages,  # type: ignore
                    temperature=0.6,
                    max_tokens=1000,
                )
                content = response.choices[0].message.content or ""
                llm_logger.debug(f"RAW LLM Name Response:\n---\n{content}\n---")

                # Add assistant's response to maintain conversation context
                messages.append({"role": "assistant", "content": content})

                # Process the response
                lines = content.strip().split("\n")
                for line in lines:
                    # Clean up the line: remove punctuation, whitespace, list markers
                    cleaned_name = re.sub(r"^[*\-–—\s\d.]+\s*", "", line.strip())
                    cleaned_name = re.sub(r"[^\w.-]+", "", cleaned_name)

                    if cleaned_name and len(cleaned_name) > 1:
                        found_packages.add(cleaned_name)
                        if len(found_packages) >= limit:
                            break

            except Exception as e:
                llm_logger.error(f"Error during package name generation: {e}")
                break  # Exit loop on API error

        return list(found_packages)[:limit]

    def _generate_metadata_for_fake_packages(
        self, package_names: List[str], query: str, batch_size: int = 3
    ) -> Dict[str, SearchResult]:
        """
        Generates full, realistic-looking metadata for a list of non-existent package names.

        Args:
            package_names: A list of package names confirmed not to exist on PyPI.
            query: The original search query, for context.
            batch_size: The number of packages to process in a single LLM call.

        Returns:
            A dictionary mapping each package name to its generated SearchResult object.
        """
        if not package_names:
            return {}

        generated_results = {}
        for i in range(0, len(package_names), batch_size):
            batch = package_names[i : i + batch_size]
            llm_logger.info(f"Generating metadata for fake packages batch: {batch}")

            prompt = self._build_metadata_prompt(batch, query)
            try:
                response = self.client.chat.completions.create(
                    model=config.default_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful assistant that knows about Python packages. "
                                "You will be given names of packages that DO NOT exist. "
                                "Your task is to generate realistic-looking PyPI metadata for them. "
                                "Return the data in the exact JSON format requested."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=4000,
                )
                content = response.choices[0].message.content
                llm_logger.debug(
                    f"RAW LLM Metadata Response for {batch}:\n---\n{content}\n---"
                )
                if not content:
                    continue

                data = self.base.parse_and_repair_json(content)
                for item in data.get("results", []):
                    try:
                        result = SearchResult(**item)
                        # Mark as non-existent but with generated data
                        result.package_exists = False
                        generated_results[result.name] = result
                    except Exception as e:
                        llm_logger.warning(
                            f"Error parsing generated metadata item: {e}\nItem: {item}"
                        )

            except Exception as e:
                llm_logger.error(
                    f"Error querying OpenRouter for metadata generation: {e}"
                )
                continue

        return generated_results

    def search_packages(self, query: str, limit: int = 20) -> SearchResponse:
        """
        Search for Python packages using a multi-step AI-driven process.

        Args:
            query: Search query for Python packages.
            limit: Maximum number of results to return.

        Returns:
            SearchResponse containing a mix of real and AI-generated package results,
            maintaining the original order of relevance.
        """
        # Step 1: Generate a list of candidate package names
        candidate_names = self._generate_package_name_candidates(query, limit)
        if not candidate_names:
            return SearchResponse()

        # Step 2: Separate real and fake packages
        real_package_names = []
        fake_package_names = []
        for name in candidate_names:
            if package_cache.package_exists(name):
                real_package_names.append(name)
            else:
                fake_package_names.append(name)

        llm_logger.info(
            f"Verified Packages - Real: {len(real_package_names)}, Fake: {len(fake_package_names)}"
        )

        # Step 3: Generate metadata for the fake packages in batches
        fake_package_metadata = self._generate_metadata_for_fake_packages(
            fake_package_names, query
        )

        # Step 4: Combine results, preserving original order
        final_results = []
        for name in candidate_names:
            if name in real_package_names:
                # For real packages, create a minimal result. The caller
                # will use the scraper to get full, accurate details.
                result = SearchResult(
                    name=name,
                    version="N/A",  # To be fetched
                    description="This is a real package. Full details will be fetched from PyPI.",
                    package_exists=True,
                    readme_cached=cache_manager.has_readme_by_name(name),
                    package_cached=cache_manager.has_package_by_name(name),
                )
                final_results.append(result)
            elif name in fake_package_metadata:
                # For fake packages, use the generated metadata
                final_results.append(fake_package_metadata[name])

        return SearchResponse(
            info={"query": query, "count": len(final_results)}, results=final_results
        )

    def _build_metadata_prompt(self, package_names: List[str], query: str) -> str:
        """Build the prompt for the AI to generate metadata for non-existent packages."""
        package_list_str = "\n".join(f"- {name}" for name in package_names)
        return f"""
The following Python packages related to "{query}" do not exist.
Please generate realistic PyPI metadata for them:
{package_list_str}

Return the data in this exact JSON format, with one entry for each requested package:
{{
    "results": [
        {{
            "name": "package-name",
            "version": "1.0.0",
            "description": "Brief, plausible description of what the package might do.",
            "summary": "One-line summary",
            "author": "Generated Author",
            "author_email": "author@example.com",
            "home_page": "https://github.com/author/package-name",
            "package_url": "https://pypi.org/project/package-name/",
            "keywords": "keyword1, keyword2",
            "license": "MIT",
            "classifiers": [
                "Development Status :: 3 - Alpha",
                "Intended Audience :: Developers",
                "License :: OSI Approved :: MIT License",
                "Programming Language :: Python :: 3"
            ],
            "requires_python": ">=3.8",
            "project_urls": {{
                "Homepage": "https://github.com/author/package-name",
                "Repository": "https://github.com/author/package-name"
            }}
        }}
    ]
}}

Ensure the 'name' field in each JSON object exactly matches one of the requested package names.
"""
```
## File: config.py
```python
"""
Configuration management for PAIPI.
"""

from __future__ import annotations

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
## File: generate_package.py
```python
"""
Docker Open Interpreter Module

A self-contained module for running Open Interpreter in a Docker container
to generate Python libraries based on PyPI descriptions and README specifications.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Configuration for library generation"""

    python_version: str = "3.11"
    cache_folder: str = "./cache"
    container_name: Optional[str] = None
    timeout_seconds: int = 3600  # 1 hour default timeout
    openai_api_key: Optional[str] = None
    model: str = "gpt-4"
    max_retries: int = 3


@dataclass
class LibrarySpec:
    """Specification for the library to generate"""

    name: str
    python_version: str
    pypi_description: str
    readme_content: str
    additional_requirements: List[str] | None = None

    def __post_init__(self) -> None:
        if self.additional_requirements is None:
            self.additional_requirements = []


class DockerOpenInterpreter:
    """
    A class to run Open Interpreter in Docker for generating Python libraries.
    """

    def __init__(self, config: GenerationConfig):
        self.config = config
        self.cache_path = Path(config.cache_folder).resolve()
        self.container_name = (
            config.container_name or f"oi-generator-{int(time.time())}"
        )

        # Ensure cache directory exists
        self.cache_path.mkdir(parents=True, exist_ok=True)

        # Setup logging for this instance
        self.logger = logging.getLogger(f"{__name__}.{self.container_name}")

        # Validate Docker installation
        self._validate_docker()

    def _validate_docker(self) -> None:
        """Validate that Docker is installed and running"""
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, check=True
            )
            self.logger.info(f"Docker found: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError) as some_error:
            raise RuntimeError("Docker is not installed or not running") from some_error

    def _create_dockerfile(self, work_dir: Path, python_version: str) -> None:
        """Create a Dockerfile for the Open Interpreter container"""
        dockerfile_content = f"""
FROM python:{python_version}-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    curl \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Install Open Interpreter
RUN pip install --no-cache-dir open-interpreter

# Create output directory
RUN mkdir -p /output

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV OPENAI_API_KEY=""

# Default command
CMD ["python", "-c", "import interpreter; print('Open Interpreter ready')"]
"""

        dockerfile_path = work_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content.strip())
        self.logger.info(f"Created Dockerfile at {dockerfile_path}")

    def _create_generation_script(self, work_dir: Path, spec: LibrarySpec) -> None:
        """Create the Python script that will run inside the container"""
        python_version = spec.python_version
        script_content = f'''
import os
import sys
import json
import traceback
from pathlib import Path
from datetime import datetime
from interpreter import interpreter

def main():
    """Main function to generate the Python library"""
    os.chdir('/output')  # FIXED: Change CWD to the mounted volume.

    try:
        # Configure interpreter
        interpreter.auto_run = True
        interpreter.offline = False

        # Set API key if provided
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            interpreter.api_key = api_key  # FIXED: Removed .llm

        # Set model
        interpreter.model = os.environ.get("MODEL", "gpt-4") # FIXED: Removed .llm

        # Library specification
        spec = {json.dumps(asdict(spec), indent=2)}

        print("="*50)
        print("STARTING LIBRARY GENERATION")
        print("="*50)
        print(f"Library: {{spec['name']}}")
        print(f"Python Version: {python_version}")
        print("="*50)

        # Create the generation prompt
        prompt = f"""
I need you to create a complete Python library called '{{spec['name']}}' based on the following specifications:

**PyPI Description:**
{{spec['pypi_description']}}

**README Content/Additional Requirements:**
{{spec['readme_content']}}

**Additional Requirements:**
{{', '.join(spec['additional_requirements']) if spec['additional_requirements'] else 'None'}}

Please create a complete, production-ready Python library with the following structure:
1. Proper package structure with __init__.py files
2. Core implementation modules
3. setup.py or pyproject.toml for packaging
4. README.md file
5. requirements.txt if needed
6. Basic tests in a tests/ directory
7. Proper documentation and docstrings

Make sure to:
- Follow Python best practices and PEP 8
- Include proper error handling
- Add type hints where appropriate
- Create meaningful examples in the README
- Ensure the code is well-documented

Save everything in the current directory, which is the designated output directory.
Start by creating the directory structure for '{{spec['name']}}', then implement each module step by step.
"""

        print("Sending prompt to Open Interpreter...")
        print("-" * 30)

        # Run the generation
        response = interpreter.chat(prompt)

        print("-" * 30)
        print("Generation completed!")

        # Create a generation summary
        summary = {{
            "library_name": spec['name'],
            "generation_timestamp": str(datetime.now()),
            "python_version": "{python_version}",
            "status": "completed",
            "output_directory": "/output"
        }}

        with open("generation_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        print("Summary saved to generation_summary.json")

        # List generated files
        output_path = Path(".")
        if output_path.exists():
            print("\\nGenerated files:")
            for file_path in output_path.rglob("*"):
                if file_path.is_file():
                    print(f"  {{file_path}}")

    except Exception as e:
        error_info = {{
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": str(datetime.now())
        }}

        print(f"ERROR: {{e}}")
        print(f"TRACEBACK:\\n{{traceback.format_exc()}}")

        # Save error info
        try:
            with open("error_log.json", "w") as f:
                json.dump(error_info, f, indent=2)
        except:
            pass

        sys.exit(1)

if __name__ == "__main__":
    main()
'''

        script_path = work_dir / "generate_library.py"
        script_path.write_text(script_content)
        self.logger.info(f"Created generation script at {script_path}")

    def _build_container(self, work_dir: Path) -> None:
        """Build the Docker container"""
        self.logger.info(f"Building Docker container: {self.container_name}")

        build_cmd = ["docker", "build", "-t", self.container_name, str(work_dir)]

        try:
            result = subprocess.run(
                build_cmd, cwd=work_dir, capture_output=True, text=True, check=True
            )
            self.logger.info("Container built successfully")
            if result.stdout:
                self.logger.debug(f"Build output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to build container: {e.stderr}")
            raise RuntimeError(f"Docker build failed: {e.stderr}") from e

    def _run_container(self, work_dir: Path) -> Dict[str, Any]:
        """Run the container and capture output"""
        output_dir = self.cache_path / f"output_{int(time.time())}"
        output_dir.mkdir(exist_ok=True)

        log_file = output_dir / "container.log"

        self.logger.info(f"Running container with output directory: {output_dir}")

        # Prepare environment variables
        env_vars = []
        if self.config.openai_api_key:
            env_vars.extend(["-e", f"OPENAI_API_KEY={self.config.openai_api_key}"])
        env_vars.extend(["-e", f"MODEL={self.config.model}"])

        run_cmd = (
            [
                "docker",
                "run",
                "--rm",
                "--name",
                f"{self.container_name}_run",
                "-v",
                f"{output_dir}:/output",
                "-v",
                f"{work_dir / 'generate_library.py'}:/workspace/generate_library.py",
            ]
            + env_vars
            + [self.container_name, "python", "/workspace/generate_library.py"]
        )

        try:
            self.logger.info("Starting container execution...")

            with open(log_file, "w", encoding="utf-8") as log_f:
                with subprocess.Popen(
                    run_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    encoding="utf-8",
                ) as process:

                    # Stream output in real-time
                    if process.stdout:
                        for line in process.stdout:
                            print(f"[CONTAINER] {line.rstrip()}")
                            log_f.write(line)
                            log_f.flush()

                    process.wait(timeout=self.config.timeout_seconds)

                    if process.returncode != 0:
                        raise subprocess.CalledProcessError(process.returncode, run_cmd)

            self.logger.info("Container execution completed successfully")

            return {
                "status": "success",
                "output_directory": str(output_dir),
                "log_file": str(log_file),
            }

        except subprocess.TimeoutExpired as te:
            self.logger.error("Container execution timed out")

            subprocess.run(
                ["docker", "kill", f"{self.container_name}_run"],
                capture_output=True,
                check=True,
            )
            raise RuntimeError(
                f"Container execution timed out after {self.config.timeout_seconds} seconds"
            ) from te

        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"Container execution failed with exit code {e.returncode}"
            )
            error_info = {
                "error": "Container execution failed",
                "exit_code": e.returncode,
            }

            # Try to read error logs
            if log_file.exists():
                error_info["logs"] = log_file.read_text(encoding="utf-8")

            raise RuntimeError(f"Container execution failed: {error_info}") from e

    def generate_library(self, spec: LibrarySpec) -> Dict[str, Any]:
        """
        Generate a Python library using Open Interpreter in Docker

        Args:
            spec: Library specification including name, description, and requirements

        Returns:
            Dict containing generation results and paths
        """
        self.logger.info(f"Starting library generation for: {spec.name}")

        # Create temporary working directory
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)

            try:
                # Create Dockerfile
                self._create_dockerfile(work_dir, self.config.python_version)

                # Create generation script
                self._create_generation_script(work_dir, spec)

                # Build container
                self._build_container(work_dir)

                # Run container
                result = self._run_container(work_dir)

                # Cleanup container image
                subprocess.run(
                    ["docker", "rmi", self.container_name],
                    capture_output=True,
                    check=False,
                )

                self.logger.info("Library generation completed successfully")
                return result

            except Exception as e:
                self.logger.error(f"Library generation failed: {e}")

                # Cleanup on failure
                subprocess.run(
                    ["docker", "rmi", self.container_name],
                    capture_output=True,
                    check=False,
                )

                raise

    def list_generated_libraries(self) -> List[Dict[str, Any]]:
        """List all generated libraries in the cache"""
        libraries = []

        for output_dir in self.cache_path.glob("output_*"):
            if output_dir.is_dir():
                summary_file = output_dir / "generation_summary.json"
                if summary_file.exists():

                    with open(summary_file, encoding="utf-8") as f:
                        summary = json.load(f)
                        summary["output_path"] = str(output_dir)
                        libraries.append(summary)

        return sorted(libraries, key=lambda x: x.get("generation_timestamp", ""))

    def cleanup_cache(self, older_than_days: int = 7) -> int:
        """Remove old generated libraries from cache"""
        cutoff_time = time.time() - (older_than_days * 24 * 3600)
        removed_count = 0

        for output_dir in self.cache_path.glob("output_*"):
            if output_dir.is_dir():
                try:
                    # Extract timestamp from directory name
                    timestamp = int(output_dir.name.split("_")[1])
                    if timestamp < cutoff_time:
                        shutil.rmtree(output_dir)
                        removed_count += 1
                        self.logger.info(f"Removed old cache directory: {output_dir}")
                except (ValueError, IndexError):
                    # Skip directories that don't match the expected naming pattern
                    pass

        return removed_count


def main() -> None:
    """Example usage of the DockerOpenInterpreter"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Python libraries using Open Interpreter in Docker"
    )
    parser.add_argument("--name", required=True, help="Library name")
    parser.add_argument("--description", required=True, help="PyPI description")
    parser.add_argument(
        "--readme", required=True, help="Path to README file or inline content"
    )
    parser.add_argument(
        "--python-version", default="3.11", help="Python version (default: 3.11)"
    )
    parser.add_argument("--cache-folder", default="./cache", help="Cache folder path")
    parser.add_argument("--openai-api-key", help="OpenAI API key")
    parser.add_argument(
        "--model", default="gpt-4", help="Model to use (default: gpt-4)"
    )
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds")
    parser.add_argument("--list", action="store_true", help="List generated libraries")
    parser.add_argument("--cleanup", type=int, help="Remove cache older than N days")

    args = parser.parse_args()

    config = GenerationConfig(
        python_version=args.python_version,
        cache_folder=args.cache_folder,
        timeout_seconds=args.timeout,
        openai_api_key=args.openai_api_key or os.environ.get("OPENAI_API_KEY"),
        model=args.model,
    )

    interpreter = DockerOpenInterpreter(config)

    if args.list:
        libraries = interpreter.list_generated_libraries()
        if libraries:
            print("Generated libraries:")
            for lib in libraries:
                print(f"  - {lib['library_name']} ({lib['generation_timestamp']})")
                print(f"    Path: {lib['output_path']}")
        else:
            print("No generated libraries found.")
        return

    if args.cleanup is not None:
        removed = interpreter.cleanup_cache(args.cleanup)
        print(f"Removed {removed} old cache directories.")
        return

    # Read README content
    readme_content = args.readme
    if Path(args.readme).exists():
        readme_content = Path(args.readme).read_text(encoding="utf-8")

    python_version = args.python_version
    # Create library specification
    spec = LibrarySpec(
        name=args.name,
        pypi_description=args.description,
        readme_content=readme_content,
        python_version=python_version,
    )

    try:
        result = interpreter.generate_library(spec)
        print("✅ Library generated successfully!")
        print(f"📁 Output directory: {result['output_directory']}")
        print(f"📋 Log file: {result['log_file']}")
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```
## File: logger.py
```python
# paipi/logger.py
"""
Dedicated logger for LLM communications.
"""

import logging
from pathlib import Path

# Create a 'logs' directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Create a logger
llm_logger = logging.getLogger("llm_comms")
llm_logger.setLevel(logging.DEBUG)

# Create a file handler which logs even debug messages
fh = logging.FileHandler(log_dir / "llm_communications.log", encoding="utf-8")
fh.setLevel(logging.DEBUG)

# Create formatter and add it to the handlers
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)

# Add the handlers to the logger
if not llm_logger.handlers:
    llm_logger.addHandler(fh)
```
## File: main.py
```python
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
from paipi.generate_package import DockerOpenInterpreter, GenerationConfig, LibrarySpec
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
```
## File: main_package_glue.py
```python
# --- new/updated imports at top of main.py ---
import io
import zipfile
from pathlib import Path
from typing import Dict

# NEW: import the generator bits


def _normalize_model(user_model: str | None) -> str:
    """
    Map friendly/legacy names to concrete API model ids used by Open Interpreter.
    Defaults to a solid general model if unknown.
    """
    if not user_model:
        return "gpt-4o-mini"  # default: fast/cheap/good

    m = user_model.strip().lower().replace("_", "-")

    MODEL_MAP: Dict[str, str] = {
        # OpenAI "frontier"
        "gpt-5": "gpt-5",  # if enabled for your key
        "gpt-4.1": "gpt-4.1",
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "o4-mini": "o4-mini",
        "o3-mini": "o3-mini",
        "o3-mini-high": "o3-mini-high",
        # Common aliases
        "gpt-4": "gpt-4o",  # alias to a modern 4o
        "gpt4": "gpt-4o",
        "gpt-4-turbo": "gpt-4o",
        # If someone passes vendor-y names, keep a best-effort default
        "claude-3.5-sonnet": "gpt-4o",
        "gemini-2.0-flash": "gpt-4o-mini",
        "mixtral-8x7b": "gpt-4o-mini",
    }
    return MODEL_MAP.get(m, "gpt-4o-mini")


def _zip_dir_to_bytes(dir_path: Path) -> bytes:
    """
    Zip a directory into memory and return raw bytes.
    """
    with io.BytesIO() as buf:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in dir_path.rglob("*"):
                if p.is_file():
                    zf.write(p, arcname=str(p.relative_to(dir_path)))
        return buf.getvalue()
```
## File: models.py
```python
"""
Pydantic models for PyPI-shaped API responses with type hints.
"""

from __future__ import annotations

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
    # Use Field to provide a distinct description for this field in OpenAPI docs
    summary: Optional[str] = Field(
        default=None, description="The short, one-line summary of the package."
    )
    description: Optional[str] = Field(
        default=None,
        description="The long description of the package, typically the README content.",
    )
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
    readme_cached: bool = Field(
        False,
        description="Whether a README has been generated and cached for this package.",
    )
    package_cached: bool = Field(
        False, description="Whether a generated package ZIP is cached for this package."
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

from __future__ import annotations

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

    def __new__(cls, db_path: Path = CACHE_DB_PATH) -> PackageCache:
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

    def load_into_memory(self) -> None:
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

    def close(self) -> None:
        """Closes the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


# Global instance to be used across the application
package_cache = PackageCache()
```
## File: pypi_scraper.py
```python
"""
PyPI Scraper client for fetching package metadata from the official JSON API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, cast

import pypi_json
from packaging.requirements import InvalidRequirement
from pydantic import ValidationError
from requests import HTTPError

from .models import (
    PackageFile,
    PackageRelease,
    ProjectDetails,
    ProjectUrls,
)

# Set up a logger for this module, following existing patterns.
scraper_logger = logging.getLogger(__name__)
# Basic config for demonstration if not configured elsewhere
logging.basicConfig(level=logging.INFO)


class PypiScraper:
    """
    A client to fetch and parse package information from the official PyPI JSON API.
    """

    def __init__(self) -> None:
        """Initialize the scraper client."""
        # The pypi_json library is synchronous and class-based.
        # We create one instance to reuse its internal requests.Session.
        self.client = pypi_json.PyPIJSON()

    async def get_project_metadata(
        self, package_name: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the raw JSON metadata for a package from PyPI.

        Args:
            package_name: The name of the package.
            version: Optional specific version of the package. If None, gets latest.

        Returns:
            A dictionary with the raw package metadata, or None if not found.
        """
        loop = asyncio.get_event_loop()
        try:
            scraper_logger.info(
                f"Fetching metadata for '{package_name}'"
                f"{' version ' + version if version else ' (latest)'}..."
            )
            # The pypi_json library is synchronous, so we run it in an executor
            # to avoid blocking the asyncio event loop.
            metadata_obj = await loop.run_in_executor(
                None, lambda: self.client.get_metadata(package_name, version)
            )

            # The returned object is a NamedTuple; convert it to a dict
            # to match the expected return type used in main.py.
            return metadata_obj._asdict()

        except InvalidRequirement:
            # This exception is raised by pypi_json for 404s.
            scraper_logger.warning(
                f"Package '{package_name}'"
                f"{' version ' + version if version else ''} not found on PyPI."
            )
            return None
        except HTTPError as e:
            # pypi_json uses requests, which raises HTTPError.
            scraper_logger.error(
                f"HTTP error fetching '{package_name}': {e.response.status_code} - {e}"
            )
            return None
        except Exception as e:
            scraper_logger.error(
                f"An unexpected error occurred while fetching '{package_name}': {e}"
            )
            return None

    async def get_project_details(self, package_name: str) -> Optional[ProjectDetails]:
        """
        Fetches detailed information for the latest version of a package.

        Args:
            package_name: The name of the package.

        Returns:
            A ProjectDetails model instance, or None if the package is not found
            or parsing fails.
        """
        metadata = await self.get_project_metadata(package_name)
        if not metadata or "info" not in metadata:
            return None

        info = metadata["info"]
        try:
            project_urls_data = info.get("project_urls")
            project_urls = (
                ProjectUrls(**project_urls_data) if project_urls_data else None
            )

            details = ProjectDetails(
                author=info.get("author"),
                author_email=info.get("author_email"),
                maintainer=info.get("maintainer"),
                maintainer_email=info.get("maintainer_email"),
                license=info.get("license"),
                keywords=info.get("keywords"),
                classifiers=info.get("classifiers", []),
                requires_python=info.get("requires_python"),
                project_urls=project_urls,
                summary=info.get("summary"),
                platform=info.get("platform"),
            )
            return details
        except ValidationError as e:
            scraper_logger.error(
                f"Pydantic validation failed for '{package_name}': {e}"
            )
            return None

    async def get_project_readme(self, package_name: str) -> Optional[str]:
        """
        Fetches only the project's long description (README).

        This is typically the full README content in Markdown or reStructuredText.
        It's separate from the short 'summary'.

        Args:
            package_name: The name of the package.

        Returns:
            The long description string, or None if not found.
        """
        metadata = await self.get_project_metadata(package_name)
        if metadata and "info" in metadata:
            return cast(Optional[str], metadata["info"].get("description"))
        return None

    async def get_all_releases(self, package_name: str) -> List[PackageRelease]:
        """
        Gets a list of all releases for a given package.

        Args:
            package_name: The name of the package.

        Returns:
            A list of PackageRelease objects.
        """
        # Fetch metadata for the project (not a specific version) to get all releases
        metadata = await self.get_project_metadata(package_name)
        if not metadata or not metadata.get("releases"):
            return []

        releases = []
        for version, release_files in metadata["releases"].items():
            if not release_files:
                continue

            is_yanked = all(f.get("yanked", False) for f in release_files)
            yanked_reason = release_files[0].get("yanked_reason") if is_yanked else None
            upload_time = release_files[0].get("upload_time_iso_8061")

            releases.append(
                PackageRelease(
                    version=version,
                    yanked=is_yanked,
                    yanked_reason=yanked_reason,
                    upload_time=upload_time,
                )
            )
        return releases

    async def get_release_files(
        self, package_name: str, version: str = "latest"
    ) -> List[PackageFile]:
        """
        Gets all package files for a specific version of a package.

        Args:
            package_name: The name of the package.
            version: The version string. Defaults to 'latest' to get the newest.

        Returns:
            A list of PackageFile objects for the specified version.
        """
        fetch_version = None if version == "latest" else version
        metadata = await self.get_project_metadata(package_name, version=fetch_version)

        if not metadata:
            return []

        # The files are under the 'urls' key in the JSON response
        files_data = metadata.get("urls", [])
        package_files = []
        try:
            for file_info in files_data:
                package_files.append(
                    PackageFile(
                        filename=file_info.get("filename"),
                        url=file_info.get("url"),
                        hashes=file_info.get("digests", {}),
                        requires_python=file_info.get("requires_python"),
                        yanked=file_info.get("yanked", False),
                        yanked_reason=file_info.get("yanked_reason"),
                        upload_time=file_info.get("upload_time_iso_8601"),
                        size=file_info.get("size"),
                        packagetype=file_info.get("packagetype", "sdist"),
                    )
                )
            return package_files
        except ValidationError as e:
            scraper_logger.error(
                f"Pydantic validation failed for files of '{package_name}': {e}"
            )
            return []
```
## File: __about__.py
```python
"""Metadata for paipi."""

__all__ = [
    "__title__",
    "__version__",
    "__description__",
    "__readme__",
    "__license__",
    "__requires_python__",
    "__status__",
]

__title__ = "paipi"
__version__ = "0.1.0"
__description__ = "PyPI search, except the backend is an LLM's pixelated memory of PyPI"
__readme__ = "README.md"
__license__ = "MIT"
__requires_python__ = ">=3.9"
__status__ = "3 - Alpha"
```
