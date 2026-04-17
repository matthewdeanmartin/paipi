from __future__ import annotations

from pathlib import Path

import pytest

import paipi.package_cache as package_cache_module


@pytest.fixture
def package_cache(tmp_path: Path):
    package_cache_module.PackageCache._instance = None
    cache = package_cache_module.PackageCache(tmp_path / "packages.db")
    try:
        yield cache
    finally:
        cache.close()
        package_cache_module.PackageCache._instance = None


def test_package_exists_normalizes_name(package_cache):
    cursor = package_cache._connection.cursor()
    cursor.execute("INSERT INTO packages (name) VALUES (?)", ("django-rest-framework",))
    cursor.execute("INSERT INTO packages (name) VALUES (?)", ("zope-interface",))
    package_cache._connection.commit()

    package_cache.load_into_memory()

    assert package_cache.package_exists("Django_REST_Framework") is True
    assert package_cache.package_exists("zope.interface") is True
    assert package_cache.package_exists("missing-package") is False


def test_update_cache_downloads_and_loads_package_names(
    monkeypatch: pytest.MonkeyPatch, package_cache
):
    html = """
    <html>
      <body>
        <a href="/simple/requests/">requests</a>
        <a href="/simple/fastapi/">fastapi</a>
      </body>
    </html>
    """

    class FakeResponse:
        text = html

        @staticmethod
        def raise_for_status() -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str, timeout: float):
            assert url == package_cache_module.PYPI_SIMPLE_URL
            assert timeout == 120.0
            return FakeResponse()

    monkeypatch.setattr(package_cache_module.httpx, "Client", FakeClient)

    package_cache.update_cache()

    assert package_cache.has_data() is True
    assert package_cache.package_exists("Requests") is True
    assert package_cache.package_exists("fast_api") is False
