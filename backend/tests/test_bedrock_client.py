"""`call_bedrock_chat()` - the shared Mantle-gateway HTTP client both
BedrockSpecificationGenerator and BedrockPromptExpander call through. Mocks
`httpx.post` so these stay fast and never touch the network.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.services.ai.bedrock_client import call_bedrock_chat


def test_returns_none_when_no_api_key_configured(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_api_key", "")
    assert call_bedrock_chat([{"role": "user", "content": "hi"}]) is None


def test_returns_message_content_on_success(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_api_key", "ABSKexample")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello from the model."}}]
    }

    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = call_bedrock_chat([{"role": "user", "content": "hi"}], system="Be nice.")

    assert result == "Hello from the model."
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer ABSKexample"
    sent_messages = call_kwargs["json"]["messages"]
    assert sent_messages[0] == {"role": "system", "content": "Be nice."}
    assert sent_messages[1] == {"role": "user", "content": "hi"}


def test_json_object_true_sets_response_format(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_api_key", "ABSKexample")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"choices": [{"message": {"content": "{}"}}]}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        call_bedrock_chat([{"role": "user", "content": "hi"}], json_object=True)

    assert mock_post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}


def test_json_object_false_omits_response_format(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_api_key", "ABSKexample")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"choices": [{"message": {"content": "text"}}]}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        call_bedrock_chat([{"role": "user", "content": "hi"}])

    assert "response_format" not in mock_post.call_args.kwargs["json"]


def test_custom_timeout_is_passed_through(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_api_key", "ABSKexample")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"choices": [{"message": {"content": "text"}}]}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        call_bedrock_chat([{"role": "user", "content": "hi"}], timeout=350.0)

    assert mock_post.call_args.kwargs["timeout"] == 350.0


def test_default_timeout_used_when_not_specified(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_api_key", "ABSKexample")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"choices": [{"message": {"content": "text"}}]}

    with patch("httpx.post", return_value=mock_response) as mock_post:
        call_bedrock_chat([{"role": "user", "content": "hi"}])

    assert mock_post.call_args.kwargs["timeout"] == 180


def test_returns_none_on_http_error(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_api_key", "ABSKexample")

    with patch("httpx.post", side_effect=RuntimeError("network down")):
        assert call_bedrock_chat([{"role": "user", "content": "hi"}]) is None


def test_returns_none_on_malformed_response(monkeypatch):
    monkeypatch.setattr(settings, "bedrock_api_key", "ABSKexample")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"unexpected": "shape"}

    with patch("httpx.post", return_value=mock_response):
        assert call_bedrock_chat([{"role": "user", "content": "hi"}]) is None
