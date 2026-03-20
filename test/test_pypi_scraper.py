from __future__ import annotations

import pytest

import paipi.pypi_scraper as pypi_scraper_module
from paipi.pypi_scraper import PypiScraper


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeResponse:
    def __init__(self, url: str, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.request = pypi_scraper_module.httpx.Request("GET", url)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise pypi_scraper_module.httpx.HTTPStatusError(
                "request failed", request=self.request, response=self
            )

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    def __init__(self, response: FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        assert url == str(self._response.request.url)
        return self._response


@pytest.mark.anyio
async def test_get_project_metadata_accepts_unknown_top_level_fields(
    monkeypatch: pytest.MonkeyPatch,
):
    scraper = PypiScraper()
    url = scraper._build_metadata_url("hvplot")
    payload = {
        "info": {"author": "HoloViz", "summary": "Plotting"},
        "ownership": {"maintainers": ["alice"]},
        "releases": {},
        "urls": [],
    }
    monkeypatch.setattr(
        pypi_scraper_module.httpx,
        "AsyncClient",
        lambda timeout: FakeAsyncClient(FakeResponse(url, 200, payload)),
    )

    metadata = await scraper.get_project_metadata("hvplot")

    assert metadata is not None
    assert metadata["ownership"] == {"maintainers": ["alice"]}


@pytest.mark.anyio
async def test_get_project_metadata_returns_none_for_404(
    monkeypatch: pytest.MonkeyPatch,
):
    scraper = PypiScraper()
    url = scraper._build_metadata_url("missing-package")
    monkeypatch.setattr(
        pypi_scraper_module.httpx,
        "AsyncClient",
        lambda timeout: FakeAsyncClient(FakeResponse(url, 404, {})),
    )

    metadata = await scraper.get_project_metadata("missing-package")

    assert metadata is None


@pytest.mark.anyio
async def test_get_all_releases_reads_upload_time_from_pypi_json_response(
    monkeypatch: pytest.MonkeyPatch,
):
    scraper = PypiScraper()
    url = scraper._build_metadata_url("plotly")
    payload = {
        "info": {"summary": "Plotly"},
        "releases": {
            "1.0.0": [
                {
                    "yanked": True,
                    "yanked_reason": "broken wheel",
                    "upload_time_iso_8601": "2024-01-02T03:04:05+00:00",
                }
            ]
        },
        "urls": [],
    }
    monkeypatch.setattr(
        pypi_scraper_module.httpx,
        "AsyncClient",
        lambda timeout: FakeAsyncClient(FakeResponse(url, 200, payload)),
    )

    releases = await scraper.get_all_releases("plotly")

    assert len(releases) == 1
    assert releases[0].yanked is True
    assert releases[0].yanked_reason == "broken wheel"
    assert releases[0].upload_time is not None
    assert releases[0].upload_time.isoformat() == "2024-01-02T03:04:05+00:00"
