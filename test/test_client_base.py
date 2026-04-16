from unittest.mock import MagicMock, patch

import pytest

from paipi.client_base import OpenRouterClientBase


@pytest.fixture
def client():
    return OpenRouterClientBase(api_key="fake-key")


def test_init_raises_error_no_api_key():
    with patch("paipi.client_base.config") as mock_config:
        mock_config.openrouter_api_key = None
        with pytest.raises(ValueError, match="OpenRouter API key is required"):
            OpenRouterClientBase()


def test_extract_json(client):
    content = '```json\n{"key": "value"}\n```'
    result = client.extract_json(content)
    assert result == {"key": "value"}

    content = '{"key": "value"}'
    result = client.extract_json(content)
    assert result == {"key": "value"}


def test_parse_and_repair_json_standard(client):
    content = '{"key": "value"}'
    result = client.parse_and_repair_json(content)
    assert result == {"key": "value"}


def test_parse_and_repair_json_markdown(client):
    content = '```json\n{"key": "value"}\n```'
    result = client.parse_and_repair_json(content)
    assert result == {"key": "value"}


@patch("untruncate_json.complete")
def test_parse_and_repair_json_untruncate(mock_untruncate, client):
    mock_untruncate.return_value = '{"key": "value"}'
    content = '{"key": "val'
    result = client.parse_and_repair_json(content)
    assert result == {"key": "value"}
    mock_untruncate.assert_called_once()


@patch("paipi.client_base.OpenRouterClientBase.ask_llm_to_fix_json")
def test_parse_and_repair_json_llm_fix(mock_llm_fix, client):
    mock_llm_fix.return_value = '{"key": "fixed"}'
    content = "invalid json"
    # We need to make sure untruncate_json.complete fails or doesn't fix it
    with patch("untruncate_json.complete", side_effect=Exception("failed")):
        result = client.parse_and_repair_json(content)
    assert result == {"key": "fixed"}
    mock_llm_fix.assert_called_once()


def test_ask_llm_to_fix_json(client):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"fixed": true}'
    client.client.chat.completions.create = MagicMock(return_value=mock_response)

    result = client.ask_llm_to_fix_json("broken")
    assert result == '{"fixed": true}'
    client.client.chat.completions.create.assert_called_once()


def test_ask_llm_to_fix_json_error(client):
    client.client.chat.completions.create = MagicMock(
        side_effect=Exception("API error")
    )
    result = client.ask_llm_to_fix_json("broken")
    assert result is None
