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
