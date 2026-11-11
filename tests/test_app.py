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


def test_gateway_denial_stops_before_document_retrieval(monkeypatch):
    def forbidden_retrieval(*args):
        raise AssertionError("Cross-department request reached retrieval")

    monkeypatch.setattr("eaaf_work.app.retrieve", forbidden_retrieval)

    def upstream(request):
        assert request.url.path == "/chat/hr/authorize"
        assert request.headers["authorization"] == "Bearer it-key"
        assert "cookie" not in request.headers
        assert json.loads(request.content) == {"model": "eaaf-mock-hr"}
        return httpx.Response(403, json={"detail": "Application key is not allowed in this chat space"})

    with TestClient(create_app(transport=httpx.MockTransport(upstream))) as client:
        response = client.post(
            "/chat/hr/completions",
            json={"model": "eaaf-mock-hr", "messages": [{"role": "user", "content": "conges"}], "use_knowledge": True},
            headers={"Authorization": "Bearer it-key", "Cookie": "ignored=yes"},
        )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_keyword_and_semantic_search_keep_department_scope():
    embedding_inputs = []

    def upstream(request):
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer hr-key"
        if request.url.path == "/chat/hr/authorize":
            return httpx.Response(204)
        if request.url.path == "/chat/hr/embeddings":
            texts = payload["input"]
            assert all("VPN" not in text for text in texts)
            embedding_inputs.append(texts)
            return httpx.Response(200, json={"data": [
                {"index": i, "embedding": vector}
                for i, vector in enumerate([[1, 0], [1, 0], [0, 1]][:len(texts)])
            ]})
        assert request.url.path == "/chat/hr/completions"
        assert "use_knowledge" not in payload
        assert "five working days" in payload["messages"][0]["content"]
        assert "VPN" not in payload["messages"][0]["content"]
        return httpx.Response(200, json={"object": "chat.completion"})

    with TestClient(create_app(transport=httpx.MockTransport(upstream))) as client:
        for mode, question in [("keyword", "conges"), ("semantic", "voyage"), ("semantic", "vacances")]:
            response = client.post(
                "/chat/hr/completions",
                json={"model": "eaaf-mock-hr", "messages": [{"role": "user", "content": question}],
                      "use_knowledge": True, "retrieval": mode},
                headers={"Authorization": "Bearer hr-key"},
            )
            assert response.status_code == 200
            assert [source["id"] for source in response.json()["sources"]] == ["hr-leave"]
    assert [len(texts) for texts in embedding_inputs] == [3, 1]


def test_gateway_timeout_is_reported_without_exposing_url():
    def upstream(request):
        raise httpx.ReadTimeout("private upstream details", request=request)

    with TestClient(create_app(transport=httpx.MockTransport(upstream))) as client:
        response = client.get("/chat/it/options")
    assert response.status_code == 504
    assert response.json() == {"detail": "Gateway request timed out"}
