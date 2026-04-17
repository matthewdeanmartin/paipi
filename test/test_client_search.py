from unittest.mock import MagicMock, patch

import pytest

from paipi.client_search import OpenRouterClientSearch, SearchGenerationError


@pytest.fixture
def client(test_caches):
    with patch("paipi.client_search.OpenAI"), patch("paipi.client_base.OpenAI"):
        return OpenRouterClientSearch(api_key="fake-key")


def test_generate_package_name_candidates(client):
    mock_response = MagicMock()
    mock_response.model = "anthropic/claude-3.5-sonnet"
    mock_response.choices[0].message.content = "pkg1\npkg2\n* pkg3\n4. pkg4"
    client.base.client.chat.completions.create = MagicMock(return_value=mock_response)

    with patch("paipi.client_base.config") as mock_config:
        mock_config.default_model = "google/gemma-4-31b-it:free"
        mock_config.openrouter_models = ["google/gemma-4-31b-it:free"]
        mock_config.rotate_models = False
        candidates, model_used, attempted_models = (
            client._generate_package_name_candidates("test query", limit=4)
        )
    assert candidates == ["pkg1", "pkg2", "pkg3", "pkg4"]
    assert model_used == "anthropic/claude-3.5-sonnet"
    assert attempted_models == ["google/gemma-4-31b-it:free"]


def test_generate_package_name_candidates_retries_after_garbage_response(client):
    bad_response = MagicMock()
    bad_response.model = "anthropic/claude-3.5-sonnet"
    bad_response.choices[0].message.content = """
    {"requests": [
    {
    "model": "openrouter/auto"
    }
    ]}
    """
    good_response = MagicMock()
    good_response.model = "anthropic/claude-3.5-sonnet"
    good_response.choices[0].message.content = "cx_Freeze\npygame"
    client.base.client.chat.completions.create = MagicMock(
        side_effect=[bad_response, good_response]
    )

    with patch("paipi.client_base.config") as mock_config:
        mock_config.default_model = "google/gemma-4-31b-it:free"
        mock_config.openrouter_models = ["google/gemma-4-31b-it:free"]
        mock_config.rotate_models = False
        candidates, _, _ = client._generate_package_name_candidates("test query", limit=2)

    assert candidates == ["cx_Freeze", "pygame"]


def test_generate_metadata_for_fake_packages(client):
    mock_response = MagicMock()
    mock_response.model = "anthropic/claude-3.5-sonnet"
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
    client.base.client.chat.completions.create = MagicMock(return_value=mock_response)

    results, models_used = client._generate_metadata_for_fake_packages(
        ["fake-pkg"], "query"
    )
    assert "fake-pkg" in results
    assert results["fake-pkg"].summary == "Fake summary"
    assert results["fake-pkg"].package_exists is False
    assert results["fake-pkg"].search_model == "anthropic/claude-3.5-sonnet"
    assert models_used == ["anthropic/claude-3.5-sonnet"]


def test_generate_metadata_rejects_name_mismatches(client):
    mock_response = MagicMock()
    mock_response.model = "anthropic/claude-3.5-sonnet"
    mock_response.choices[
        0
    ].message.content = """
    {
        "results": [
            {
                "name": "fake_pkg",
                "version": "1.0.0",
                "summary": "Fake summary"
            }
        ]
    }
    """
    client.base.client.chat.completions.create = MagicMock(return_value=mock_response)

    results, models_used = client._generate_metadata_for_fake_packages(
        ["fake-pkg"], "query"
    )

    assert results == {}
    assert models_used == ["anthropic/claude-3.5-sonnet"]


def test_search_packages_full_flow(client, test_caches):
    cm, pc = test_caches

    # Setup package cache: pkg1 is real, pkg2 is fake
    cursor = pc._connection.cursor()
    cursor.execute("INSERT INTO packages (name) VALUES (?)", ("pkg1",))
    pc._connection.commit()
    pc._package_names = None  # Force reload

    # Mock candidate generation
    mock_resp_names = MagicMock()
    mock_resp_names.model = "google/gemma-4-31b-it:free"
    mock_resp_names.choices[0].message.content = "pkg1\npkg2"

    # Mock metadata generation for fake packages
    mock_resp_meta = MagicMock()
    mock_resp_meta.model = "anthropic/claude-3.5-sonnet"
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

    client.base.client.chat.completions.create = MagicMock(
        side_effect=[mock_resp_names, mock_resp_meta]
    )

    response = client.search_packages("query", limit=2)

    assert len(response.results) == 2
    assert [r.name for r in response.results] == ["pkg1", "pkg2"]

    pkg1 = next(r for r in response.results if r.name == "pkg1")
    assert pkg1.package_exists is True
    assert pkg1.search_model == "google/gemma-4-31b-it:free"

    pkg2 = next(r for r in response.results if r.name == "pkg2")
    assert pkg2.package_exists is False
    assert pkg2.version == "2.0.0"
    assert pkg2.search_model == "anthropic/claude-3.5-sonnet"
    assert response.info["model_used"] == "google/gemma-4-31b-it:free"
    assert response.info["metadata_models_used"] == ["anthropic/claude-3.5-sonnet"]


def test_generate_package_name_candidates_raises_real_api_error(client):
    client.base.client.chat.completions.create = MagicMock(
        side_effect=Exception(
            "Error code: 404 - {'error': {'message': 'No endpoints found for anthropic/claude-3.5-sonnet.', 'code': 404}}"
        )
    )

    with pytest.raises(
        SearchGenerationError,
        match="No endpoints found for anthropic/claude-3.5-sonnet.",
    ):
        client._generate_package_name_candidates("bad config", limit=3)
