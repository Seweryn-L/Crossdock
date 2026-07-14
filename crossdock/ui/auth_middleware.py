"""Session-based access control for all NiceGUI pages.

Unauthenticated requests are redirected to /login. Sessions expire
after a configurable idle period (logout on inactivity).
"""

import time

from nicegui import app
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from crossdock.config import get_settings

UNRESTRICTED_PAGES = {"/login"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in UNRESTRICTED_PAGES or path.startswith("/_nicegui") or path.startswith("/static"):
            return await call_next(request)

        if not app.storage.user.get("authenticated", False):
            return RedirectResponse(f"/login?redirect_to={path}")

        max_idle_seconds = get_settings().session_max_idle_minutes * 60
        now = time.time()
        last_activity = app.storage.user.get("last_activity", now)
        if now - last_activity > max_idle_seconds:
            app.storage.user.clear()
            return RedirectResponse("/login")
        app.storage.user["last_activity"] = now

        return await call_next(request)
