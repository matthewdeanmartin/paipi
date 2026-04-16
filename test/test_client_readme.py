from unittest.mock import MagicMock, patch

import pytest

from paipi.client_readme import OpenRouterClientReadMe
from paipi.models import ReadmeRequest


@pytest.fixture
def client():
    # Patch OpenAI before initializing the client
    with patch("paipi.client_readme.OpenAI"), patch("paipi.client_base.OpenAI"):
        return OpenRouterClientReadMe(api_key="fake-key")


def test_generate_readme_legacy(client):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"title": "Test", "description": "Desc"}'
    )
    client.client.chat.completions.create = MagicMock(return_value=mock_response)

    req = ReadmeRequest(name="test-pkg")
    readme = client.generate_readme(req)

    assert "# Test" in readme
    assert "## Description" in readme
    assert "Desc" in readme


def test_generate_readme_legacy_error(client):
    client.client.chat.completions.create = MagicMock(
        side_effect=Exception("API error")
    )

    req = ReadmeRequest(name="test-pkg", summary="Short summary")
    readme = client.generate_readme(req)

    assert "# test-pkg" in readme
    assert "Short summary" in readme
    assert "README generation failed" in readme


def test_generate_readme_markdown(client):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "# Markdown README\n\nSome content."
    client.client.chat.completions.create = MagicMock(return_value=mock_response)

    req = ReadmeRequest(name="test-pkg")
    readme = client.generate_readme_markdown(req)

    assert "# Markdown README" in readme
    assert "Some content." in readme


def test_generate_readme_markdown_with_fences(client):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "```markdown\n# Fenced README\n```"
    client.client.chat.completions.create = MagicMock(return_value=mock_response)

    req = ReadmeRequest(name="test-pkg")
    readme = client.generate_readme_markdown(req)

    assert "# Fenced README" in readme
    assert "```markdown" not in readme


def test_generate_readme_markdown_error(client):
    client.client.chat.completions.create = MagicMock(
        side_effect=Exception("API error")
    )

    req = ReadmeRequest(name="test-pkg", summary="Short summary")
    readme = client.generate_readme_markdown(req)

    assert "# test-pkg" in readme
    assert "README generation failed" in readme
