from __future__ import annotations

from pathlib import Path

import pytest

from paipi.cache_manager import CacheManager
from paipi.models import ReadmeRequest, SearchResponse, SearchResult


@pytest.fixture
def cache_manager(tmp_path: Path):
    manager = CacheManager(tmp_path / "cache")
    try:
        yield manager
    finally:
        manager.close()


def test_cache_manager_initializes_expected_tables(cache_manager: CacheManager):
    cursor = cache_manager._connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    tables = {row[0] for row in cursor.fetchall()}

    assert {"search_cache", "readme_cache", "package_cache"} <= tables


def test_search_cache_round_trip(cache_manager: CacheManager):
    response = SearchResponse(
        info={"source": "unit-test"},
        results=[
            SearchResult(name="demo-package", version="1.2.3", summary="Example package")
        ],
    )

    cache_manager.cache_search_results("  Demo Query  ", response)
    cached = cache_manager.get_cached_search("demo query")

    assert cached is not None
    assert cached.model_dump() == response.model_dump()
    assert cache_manager.get_cache_stats()["search"] == 1


def test_get_all_cached_searches_skips_invalid_entries(cache_manager: CacheManager):
    valid_response = SearchResponse(
        info={"source": "unit-test"},
        results=[SearchResult(name="valid-package", version="0.1.0")],
    )
    cache_manager.cache_search_results("valid", valid_response)

    cursor = cache_manager._connection.cursor()
    cursor.execute(
        """
        INSERT INTO search_cache (query_key, original_query, results_json)
        VALUES (?, ?, ?)
        """,
        ("broken", "broken", '{"results": "not-a-list"}'),
    )
    cache_manager._connection.commit()

    cached_searches = cache_manager.get_all_cached_searches()

    assert len(cached_searches) == 1
    assert cached_searches[0].results[0].name == "valid-package"


def test_cache_readme_persists_to_database_and_filesystem(cache_manager: CacheManager):
    request = ReadmeRequest(name="demo-package", summary="Summary")
    markdown = "# demo-package\n"

    cache_manager.cache_readme(request, markdown)

    assert cache_manager.get_cached_readme(request) == markdown
    assert cache_manager.has_readme_by_name("demo-package") is True
    assert cache_manager.get_readme_by_name("demo-package") == markdown
    assert (
        cache_manager.packages_dir / "demo-package" / "README.md"
    ).read_text(encoding="utf-8") == markdown


def test_get_cached_package_removes_stale_database_entries(cache_manager: CacheManager):
    cache_manager.cache_package("demo-package", b"zip-bytes")
    zip_path = cache_manager.packages_dir / "demo-package" / "demo-package.zip"
    zip_path.unlink()

    assert cache_manager.get_cached_package("demo-package") is None
    assert cache_manager.has_package_by_name("demo-package") is False


def test_generate_stub_package_creates_installable_structure(cache_manager: CacheManager):
    zip_bytes = cache_manager.generate_stub_package(
        "demo-package",
        {"version": "2.0.0", "author": "Copilot", "description": "A demo package"},
    )

    stub_archive = cache_manager.cache_dir / "stub.zip"
    stub_archive.write_bytes(zip_bytes)

    import zipfile

    with zipfile.ZipFile(stub_archive) as archive:
        names = {name.replace("\\", "/") for name in archive.namelist()}
        assert {
            "pyproject.toml",
            "README.md",
            "demo_package/__init__.py",
            "MANIFEST.in",
            "LICENSE",
        } <= names
        init_text = archive.read("demo_package/__init__.py").decode("utf-8")
        assert '__version__ = "2.0.0"' in init_text
        assert 'return f"Hello from demo-package!"' in init_text
