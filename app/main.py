from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.responses import Response

from app.api import assistant, auth, google_auth, oauth, projects, tasks
from app.config import FRONTEND_ORIGINS
from app.mcp.server import mcp

STATIC_DIR = Path(__file__).resolve().parent / "static"
mcp_app = mcp.http_app(path="/mcp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_app.lifespan(app):
        yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(FRONTEND_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

app.include_router(auth.router)
app.include_router(google_auth.router)
app.include_router(oauth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(assistant.router)


@app.middleware("http")
async def prevent_auth_response_caching(request: Request, call_next) -> Response:
    response = await call_next(request)
    if request.url.path.startswith("/auth/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Hello World"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(
        STATIC_DIR / "favicon.ico",
        media_type="image/x-icon",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/icon.svg", include_in_schema=False)
def icon_svg():
    return FileResponse(
        STATIC_DIR / "icon.svg",
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/icon.png", include_in_schema=False)
def icon_png():
    return FileResponse(
        STATIC_DIR / "icon.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# Keep this catch-all mount last so ordinary FastAPI routes remain reachable.
app.mount("/", mcp_app)
