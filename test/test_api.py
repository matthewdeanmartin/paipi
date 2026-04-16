from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from paipi.main import app
from paipi.models import SearchResponse, SearchResult


@pytest.fixture
def client(test_caches):
    # Mock the package_cache methods that are called in the startup event
    # to avoid real network calls or background thread issues.
    with patch("paipi.main.package_cache.load_into_memory"), patch(
        "paipi.main.package_cache.update_cache"
    ):
        with TestClient(app) as c:
            yield c


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome to PAIPI" in response.json()["message"]


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@patch("paipi.main.ai_client.search_packages")
@patch("paipi.main.pypi_scraper.get_project_metadata")
def test_search_endpoint(mock_pypi, mock_ai, client):
    # Mock AI response
    mock_ai.return_value = SearchResponse(
        info={"query": "test"},
        results=[SearchResult(name="pkg1", version="1.0.0", package_exists=True)],
    )
    # Mock PyPI scraper
    mock_pypi.return_value = {
        "info": {
            "version": "1.0.1",
            "summary": "Updated summary",
            "package_url": "https://pypi.org/project/pkg1/",
        }
    }

    response = client.get("/search?q=test")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["name"] == "pkg1"
    assert data["results"][0]["version"] == "1.0.1"


@patch("paipi.main.readme_client.generate_readme_markdown")
def test_readme_endpoint(mock_readme, client):
    mock_readme.return_value = "# Generated README"

    response = client.post("/readme", json={"name": "test-pkg"})
    assert response.status_code == 200
    assert response.text == "# Generated README"


def test_cache_stats_endpoint(client):
    response = client.get("/cache/stats")
    assert response.status_code == 200
    assert "cache_stats" in response.json()


def test_clear_cache_endpoint(client):
    response = client.delete("/cache/clear?cache_type=search")
    assert response.status_code == 200
    assert "Cleared search cache(s)" in response.json()["message"]
