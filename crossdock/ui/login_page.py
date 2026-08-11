"""Login page (/login). UI texts in Polish."""

from nicegui import app, run, ui

from crossdock.services.auth import AuthService
from crossdock.storage.database import session_scope
from crossdock.ui.layout import ensure_theme


def _authenticate_blocking(username: str, password: str) -> dict[str, str] | None:
    """Runs in a worker thread: argon2 verification takes tens of ms."""
    with session_scope() as session:
        user = AuthService(session).authenticate(username, password)
        if user is None:
            return None
        return {"username": user.username, "role": user.role.value}


@ui.page("/login")
def login_page(redirect_to: str = "/") -> None:
    if app.storage.user.get("authenticated", False):
        ui.navigate.to("/")
        return

    ensure_theme()

    async def try_login() -> None:
        result = await run.io_bound(_authenticate_blocking, username.value, password.value)
        if result is None:
            ui.notify("Nieprawidłowa nazwa użytkownika lub hasło", color="negative")
            return
        app.storage.user.update(
            authenticated=True,
            username=result["username"],
            role=result["role"],
        )
        ui.navigate.to(redirect_to)

    with ui.element("div").classes("cd-login-wrap"), ui.element("div").classes("cd-login-card"):
        ui.label("Crossdock").classes("cd-login-brand")
        ui.label("System optymalizacji cross-dockingu").classes("cd-login-sub")
        username = ui.input("Nazwa użytkownika").props("autofocus outlined").classes("w-full")
        password = (
            ui.input("Hasło", password=True, password_toggle_button=True)
            .props("outlined")
            .classes("w-full")
        )
        password.on("keydown.enter", try_login)
        ui.button("Zaloguj się", on_click=try_login).props(
            "unelevated color=primary no-caps"
        ).classes("w-full mt-3")
