import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from paipi.pypi_scraper import PypiScraper
from paipi.models import ProjectDetails, PackageRelease, PackageFile

@pytest.fixture
def scraper():
    return PypiScraper()

@pytest.fixture
def anyio_backend():
    return 'asyncio'

def test_build_metadata_url(scraper):
    assert scraper._build_metadata_url("requests") == "https://pypi.org/pypi/requests/json"
    assert scraper._build_metadata_url("requests", "2.25.1") == "https://pypi.org/pypi/requests/2.25.1/json"

@pytest.mark.anyio
async def test_get_project_metadata_success(scraper):
    mock_response = {
        "info": {"name": "test-pkg", "version": "1.0.0"},
        "releases": {"1.0.0": []}
    }
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_response,
            raise_for_status=lambda: None
        )
        # Since it's an async context manager, we need to mock __aenter__
        mock_get.return_value = MagicMock()
        mock_get.return_value.__aenter__.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_response,
            raise_for_status=lambda: None
        )
        
        # Actually, httpx.AsyncClient.get is an async method
        mock_get.return_value = MagicMock()
        mock_get.side_effect = None
        mock_get.return_value = MagicMock()
        
        # Better way to mock httpx AsyncClient
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None
            )
            
            result = await scraper.get_project_metadata("test-pkg")
            assert result == mock_response

@pytest.mark.anyio
async def test_get_project_metadata_404(scraper):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MagicMock(
            status_code=404,
            raise_for_status=lambda: None
        )
        
        result = await scraper.get_project_metadata("non-existent")
        assert result is None

@pytest.mark.anyio
async def test_get_project_metadata_http_error(scraper):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock(status_code=500)
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_resp)
        mock_get.return_value = mock_resp
        
        result = await scraper.get_project_metadata("error-pkg")
        assert result is None

@pytest.mark.anyio
async def test_get_project_details(scraper):
    mock_metadata = {
        "info": {
            "author": "Author Name",
            "author_email": "author@example.com",
            "summary": "A test package",
            "version": "1.0.0",
            "project_urls": {"homepage": "https://github.com/test/test"}
        }
    }
    with patch.object(scraper, "get_project_metadata", return_value=mock_metadata):
        details = await scraper.get_project_details("test-pkg")
        assert isinstance(details, ProjectDetails)
        assert details.author == "Author Name"
        assert details.summary == "A test package"
        assert details.project_urls.homepage == "https://github.com/test/test"

@pytest.mark.anyio
async def test_get_project_readme(scraper):
    mock_metadata = {
        "info": {
            "description": "# My Project README"
        }
    }
    
    with patch.object(scraper, "get_project_metadata", return_value=mock_metadata):
        readme = await scraper.get_project_readme("test-pkg")
        assert readme == "# My Project README"

@pytest.mark.anyio
async def test_get_all_releases(scraper):
    mock_metadata = {
        "releases": {
            "1.0.0": [{"upload_time_iso_8601": "2023-01-01T00:00:00Z", "yanked": False}],
            "1.1.0": [{"upload_time_iso_8601": "2023-02-01T00:00:00Z", "yanked": True, "yanked_reason": "bug"}]
        }
    }
    
    with patch.object(scraper, "get_project_metadata", return_value=mock_metadata):
        releases = await scraper.get_all_releases("test-pkg")
        assert len(releases) == 2
        assert any(r.version == "1.0.0" and not r.yanked for r in releases)
        assert any(r.version == "1.1.0" and r.yanked and r.yanked_reason == "bug" for r in releases)

@pytest.mark.anyio
async def test_get_release_files(scraper):
    mock_metadata = {
        "urls": [
            {
                "filename": "test-pkg-1.0.0.tar.gz",
                "url": "https://files.pythonhosted.org/test-pkg-1.0.0.tar.gz",
                "digests": {"sha256": "abc"},
                "size": 1234
            }
        ]
    }
    
    with patch.object(scraper, "get_project_metadata", return_value=mock_metadata):
        files = await scraper.get_release_files("test-pkg", "1.0.0")
        assert len(files) == 1
        assert isinstance(files[0], PackageFile)
        assert files[0].filename == "test-pkg-1.0.0.tar.gz"
        assert files[0].size == 1234
