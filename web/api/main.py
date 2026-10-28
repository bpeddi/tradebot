import asyncio
import contextlib
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

from web.api import scheduler
from web.api.deps import decode_token
from web.api.routers import auth as auth_router
from web.api.routers import bot, config, schedule as schedule_router
from web.api.routers import trades

_PUBLIC_PATHS = {"/api/auth/login", "/api/auth/register"}


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(scheduler.scheduler_loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


class JWTMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        path = request.url.path
        if (
            request.method == "OPTIONS"
            or path in _PUBLIC_PATHS
            or not path.startswith("/api/")
        ):
            return await call_next(request)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        try:
            decode_token(auth_header[7:])
        except Exception:
            return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)
        return await call_next(request)


app = FastAPI(title="mytradebot", lifespan=lifespan)

_extra = os.environ.get("CORS_ORIGIN", "")
_origins = [_extra] if _extra else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Local dev only: the Vite dev server's port varies machine-to-machine
    # (other projects often already hold the usual 5173-ish ports), so match
    # any localhost port instead of hardcoding one. In production the built
    # frontend is served same-origin by this app, so CORS doesn't apply.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JWTMiddleware)

app.include_router(auth_router.router, prefix="/api/auth")
app.include_router(config.router, prefix="/api/config")
app.include_router(bot.router, prefix="/api/bot")
app.include_router(trades.router, prefix="/api/trades")
app.include_router(schedule_router.router, prefix="/api/schedule")

# Serve the built React app in production
_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")
