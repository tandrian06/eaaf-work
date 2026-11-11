import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

ASSETS = Path(__file__).resolve().parents[1] / "chat"
SPACES = {"global", "hr", "it", "marketing"}
PAGE_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
    "Referrer-Policy": "no-referrer",
}


def canonical_space(space: str) -> str:
    canonical = space.lower()
    if canonical not in SPACES:
        raise HTTPException(404, "Chat space not found")
    return canonical


def create_app(gateway_url: str | None = None, transport=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(
            base_url=gateway_url or os.getenv("EAAF_GATEWAY_URL", "http://127.0.0.1:8000"),
            timeout=60,
            trust_env=False,
            transport=transport,
        ) as gateway:
            app.state.gateway = gateway
            yield

    app = FastAPI(title="EAAF Work", lifespan=lifespan)
    app.mount("/chat-assets", StaticFiles(directory=ASSETS), name="chat-assets")

    @app.get("/", include_in_schema=False)
    async def home():
        return RedirectResponse("/chat/global")

    @app.get("/chat/{space}", include_in_schema=False, response_model=None)
    async def chat(space: str):
        canonical = canonical_space(space)
        if space != canonical:
            return RedirectResponse(f"/chat/{canonical}")
        return FileResponse(ASSETS / "index.html", headers=PAGE_HEADERS)

    async def forward(request: Request, path: str, body: bytes | None = None) -> Response:
        headers = {
            name: request.headers[name]
            for name in ("authorization", "content-type")
            if name in request.headers
        }
        try:
            upstream = await request.app.state.gateway.request(
                request.method, path, content=body, headers=headers
            )
        except httpx.TimeoutException as error:
            raise HTTPException(504, "Gateway request timed out") from error
        except httpx.RequestError as error:
            raise HTTPException(502, "Gateway unavailable") from error
        if upstream.is_redirect or "application/json" not in upstream.headers.get("content-type", ""):
            raise HTTPException(502, "Gateway returned an unexpected response")
        return Response(
            upstream.content,
            status_code=upstream.status_code,
            media_type="application/json",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/chat/{space}/options")
    async def options(space: str, request: Request):
        return await forward(request, f"/chat/{canonical_space(space)}/options")

    @app.post("/chat/{space}/completions")
    async def complete(space: str, request: Request):
        path = f"/chat/{canonical_space(space)}/completions"
        return await forward(request, path, await request.body())

    return app


app = create_app()
