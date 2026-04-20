import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

# Mocking before importing app to avoid unwanted side effects
with patch("paipi.cache_manager.CacheManager._init_db"), \
     patch("paipi.package_cache.PackageCache._init_db"):
    from paipi.main import app

from paipi.client_search import SearchGenerationError
from paipi.models import SearchResult, SearchResponse

@pytest.fixture
def client(tmp_path):
    # Setup temporary paths for cache
    test_cache_dir = tmp_path / "pypi_cache"
    test_cache_dir.mkdir()
    (test_cache_dir / "packages").mkdir()
    
    test_cache_dir / "cache.db"
    test_package_db_path = tmp_path / "paipi_cache.db"

    with patch("paipi.main.cache_manager") as mock_cm, \
         patch("paipi.main.package_cache") as mock_pc, \
         patch("paipi.main.ai_client") as mock_ai, \
         patch("paipi.main.readme_client") as mock_readme, \
         patch("paipi.main.CACHE_DB_PATH", test_package_db_path):
        
        # Configure mocks
        mock_cm.cache_dir = test_cache_dir
        mock_cm.get_cache_stats.return_value = {"search": 0, "readme": 0, "package": 0}
        mock_cm.get_readme_metadata_by_name.return_value = {}
        mock_cm.get_package_metadata_by_name.return_value = {}
        
        # Ensure AI clients return something sensible by default to avoid validation errors
        mock_ai.search_packages.return_value = SearchResponse(
            results=[SearchResult(name="default-pkg", version="0.1.0", summary="summary")],
            info={"query": "default", "count": 1}
        )
        mock_readme.generate_readme.return_value = "# README"
        mock_readme.generate_readme_markdown.return_value = "# README"
        mock_readme.generate_readme_markdown_with_model.return_value = (
            "# README",
            "anthropic/claude-3.5-sonnet",
        )
        
        app.dependency_overrides = {}  # Clear overrides
        with TestClient(app) as client:
            yield client

def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "<app-root" in response.text
    assert response.headers["content-type"].startswith("text/html")

def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_search_packages_with_query(client):
    # Setup mocks on the instance already patched in the fixture
    with patch("paipi.main.ai_client.search_packages") as mock_search, \
         patch("paipi.pypi_scraper.PypiScraper.get_project_metadata", new_callable=AsyncMock) as mock_get_metadata:
        
        mock_search.return_value = SearchResponse(
            results=[SearchResult(name="test-pkg", version="0.1.0", summary="AI Summary")],
            info={"query": "test", "count": 1}
        )
        mock_get_metadata.return_value = {
            "info": {
                "version": "1.0.0",
                "summary": "Real Summary",
                "description": "Real Description",
                "author": "Author"
            }
        }
        
        with patch("paipi.main.cache_manager.get_cached_search", return_value=None), \
             patch("paipi.main.cache_manager.cache_search_results"), \
             patch("paipi.main.cache_manager.cache_readme"):
            
            response = client.get("/api/search?q=test")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["name"] == "test-pkg"
            assert data["results"][0]["version"] == "1.0.0"

def test_search_packages_empty_query(client):
    with patch("paipi.main.cache_manager.get_all_cached_searches", return_value=[]):
        response = client.get("/api/search?q=")
        assert response.status_code == 200
        assert response.json()["results"] == []


def test_search_packages_surfaces_ai_error_details(client):
    with patch(
        "paipi.main.ai_client.search_packages",
        side_effect=SearchGenerationError(
            "No endpoints found for anthropic/claude-3.5-sonnet."
        ),
    ), patch("paipi.main.cache_manager.get_cached_search", return_value=None):
        response = client.get("/api/search?q=framework13")

    assert response.status_code == 502
    assert (
        response.json()["detail"]
        == "No endpoints found for anthropic/claude-3.5-sonnet."
    )

def test_generate_readme(client):
    with patch("paipi.main.readme_client.generate_readme", return_value="# Generated"), \
         patch("paipi.main.readme_client.generate_readme_markdown_with_model", return_value=("# Generated README", "anthropic/claude-3.5-sonnet")):
        
        with patch("paipi.main.cache_manager.get_cached_readme", return_value=None), \
             patch("paipi.main.cache_manager.cache_readme"):
            
            response = client.post("/api/readme", json={
                "name": "test-pkg",
                "summary": "test summary",
                "description": "test desc",
                "install_cmd": "pip install test-pkg"
            })
            
            assert response.status_code == 200
            assert response.text == "# Generated README"
            assert response.headers["content-type"] == "text/markdown; charset=utf-8"
            assert response.headers["x-paipi-model-used"] == "anthropic/claude-3.5-sonnet"

@patch("paipi.main.DockerOpenInterpreter.generate_library")
@patch("paipi.main._zip_dir_to_bytes")
def test_generate_package(mock_zip, mock_gen, client, tmp_path):
    mock_gen.return_value = {"output_directory": str(tmp_path / "output")}
    mock_zip.return_value = b"fake-zip-content"
    
    with patch("paipi.main.cache_manager.get_cached_package", return_value=None), \
         patch("paipi.main.cache_manager.cache_package"):
        
        response = client.post("/api/generate_package", json={
            "readme_markdown": "# README",
            "metadata": {"name": "test-pkg"}
        })
        
        assert response.status_code == 200
        assert response.content == b"fake-zip-content"
        assert response.headers["content-type"] == "application/zip"

def test_cache_stats(client):
    with patch("paipi.main.cache_manager.get_cache_stats", return_value={"search": 5, "readme": 2, "package": 1}):
        response = client.get("/api/cache/stats")
        assert response.status_code == 200
        assert response.json()["cache_stats"]["search"] == 5

def test_clear_cache(client):
    with patch("paipi.main.cache_manager.clear_cache") as mock_clear:
        response = client.delete("/api/cache/clear?cache_type=search")
        assert response.status_code == 200
        mock_clear.assert_called_once_with("search")

def test_availability(client):
    with patch("paipi.main.cache_manager.has_readme_by_name", return_value=True), \
         patch("paipi.main.cache_manager.has_package_by_name", return_value=False), \
         patch("paipi.main.cache_manager.get_readme_metadata_by_name", return_value={"model": "anthropic/claude-3.5-sonnet"}), \
         patch("paipi.main.cache_manager.get_package_metadata_by_name", return_value={}):
        response = client.get("/api/availability?name=test-pkg")
        assert response.status_code == 200
        assert response.json()["readme_cached"] is True
        assert response.json()["package_cached"] is False
        assert response.json()["readme_model"] == "anthropic/claude-3.5-sonnet"

def test_availability_batch(client):
    with patch("paipi.main.cache_manager.has_readme_by_name", return_value=True), \
         patch("paipi.main.cache_manager.has_package_by_name", return_value=True):
        response = client.post("/api/availability/batch", json={"names": ["pkg1", "pkg2"]})
        assert response.status_code == 200
        assert len(response.json()["items"]) == 2

def test_get_readme_by_name(client):
    with patch("paipi.main.cache_manager.get_readme_by_name", return_value="# Content"), \
         patch("paipi.main.cache_manager.get_readme_metadata_by_name", return_value={"model": "anthropic/claude-3.5-sonnet"}):
        response = client.get("/api/readme/by-name/test-pkg")
        assert response.status_code == 200
        assert response.text == "# Content"
        assert response.headers["x-paipi-model-used"] == "anthropic/claude-3.5-sonnet"

def test_get_readme_by_name_not_found(client):
    with patch("paipi.main.cache_manager.get_readme_by_name", return_value=None):
        response = client.get("/api/readme/by-name/test-pkg")
        assert response.status_code == 404

def test_search_history(client):
    with patch("paipi.main.cache_manager.get_search_history", return_value=[{"query": "test", "count": 1, "created_at": "now"}]):
        response = client.get("/api/search/history")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
