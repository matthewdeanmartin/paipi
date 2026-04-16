from unittest.mock import MagicMock, patch

import pytest

from paipi.client_search import OpenRouterClientSearch


@pytest.fixture
def client(test_caches):
    with patch("paipi.client_search.OpenAI"), patch("paipi.client_base.OpenAI"):
        return OpenRouterClientSearch(api_key="fake-key")


def test_generate_package_name_candidates(client):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "pkg1\npkg2\n* pkg3\n4. pkg4"
    client.client.chat.completions.create = MagicMock(return_value=mock_response)

    candidates = client._generate_package_name_candidates("test query", limit=4)
    assert set(candidates) == {"pkg1", "pkg2", "pkg3", "pkg4"}
    assert len(candidates) == 4


def test_generate_metadata_for_fake_packages(client):
    mock_response = MagicMock()
    mock_response.choices[
        0
    ].message.content = """
    {
        "results": [
            {
                "name": "fake-pkg",
                "version": "1.0.0",
                "summary": "Fake summary",
                "description": "Fake desc"
            }
        ]
    }
    """
    client.client.chat.completions.create = MagicMock(return_value=mock_response)

    results = client._generate_metadata_for_fake_packages(["fake-pkg"], "query")
    assert "fake-pkg" in results
    assert results["fake-pkg"].summary == "Fake summary"
    assert results["fake-pkg"].package_exists is False


def test_search_packages_full_flow(client, test_caches):
    cm, pc = test_caches

    # Setup package cache: pkg1 is real, pkg2 is fake
    cursor = pc._connection.cursor()
    cursor.execute("INSERT INTO packages (name) VALUES (?)", ("pkg1",))
    pc._connection.commit()
    pc._package_names = None  # Force reload

    # Mock candidate generation
    mock_resp_names = MagicMock()
    mock_resp_names.choices[0].message.content = "pkg1\npkg2"

    # Mock metadata generation for fake packages
    mock_resp_meta = MagicMock()
    mock_resp_meta.choices[
        0
    ].message.content = """
    {
        "results": [
            {
                "name": "pkg2",
                "version": "2.0.0",
                "summary": "Pkg2 summary"
            }
        ]
    }
    """

    client.client.chat.completions.create = MagicMock(
        side_effect=[mock_resp_names, mock_resp_meta]
    )

    response = client.search_packages("query", limit=2)

    assert len(response.results) == 2
    names = {r.name for r in response.results}
    assert names == {"pkg1", "pkg2"}

    pkg1 = next(r for r in response.results if r.name == "pkg1")
    assert pkg1.package_exists is True

    pkg2 = next(r for r in response.results if r.name == "pkg2")
    assert pkg2.package_exists is False
    assert pkg2.version == "2.0.0"
