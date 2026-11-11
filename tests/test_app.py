import json

import httpx
from fastapi.testclient import TestClient

from eaaf_work.app import create_app


def test_chat_pages_and_assets():
    with TestClient(create_app()) as client:
        home = client.get("/", follow_redirects=False)
        assert home.headers["location"] == "/chat/global"
        assert client.get("/chat/HR", follow_redirects=False).headers["location"] == "/chat/hr"
        assert client.get("/chat/unknown").status_code == 404
        page = client.get("/chat/hr")
        assert "/chat-assets/chat.css" in page.text
        assert "connect-src 'self'" in page.headers["content-security-policy"]
        assert client.get("/chat-assets/chat.css").status_code == 200


def test_gateway_retains_space_auth_and_rag_input():
    def upstream(request):
        assert request.url.path == "/chat/hr/completions"
        assert request.headers["authorization"] == "Bearer local-test-key"
        assert "cookie" not in request.headers
        assert json.loads(request.content)["use_knowledge"] is True
        return httpx.Response(403, json={"detail": "Application key is not allowed in this chat space"})

    with TestClient(create_app(transport=httpx.MockTransport(upstream))) as client:
        response = client.post(
            "/chat/hr/completions",
            json={"use_knowledge": True},
            headers={"Authorization": "Bearer local-test-key", "Cookie": "ignored=yes"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "Application key is not allowed in this chat space"
    assert response.headers["cache-control"] == "no-store"


def test_gateway_timeout_is_reported_without_exposing_url():
    def upstream(request):
        raise httpx.ReadTimeout("private upstream details", request=request)

    with TestClient(create_app(transport=httpx.MockTransport(upstream))) as client:
        response = client.get("/chat/it/options")
    assert response.status_code == 504
    assert response.json() == {"detail": "Gateway request timed out"}
