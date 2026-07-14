"""Repositories — the only place that touches ORM sessions directly."""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from crossdock.domain.models import Role, User
from crossdock.storage.tables import AuditLogRow, UserRow


def _to_domain_user(row: UserRow) -> User:
    return User(
        id=row.id,
        username=row.username,
        role=Role(row.role),
        is_active=row.is_active,
    )


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> User | None:
        row = self._get_row(username)
        return _to_domain_user(row) if row else None

    def get_password_hash(self, username: str) -> str | None:
        row = self._get_row(username)
        return row.password_hash if row else None

    def add(self, username: str, password_hash: str, role: Role) -> User:
        row = UserRow(username=username, password_hash=password_hash, role=role.value)
        self._session.add(row)
        self._session.flush()
        return _to_domain_user(row)

    def update_password_hash(self, username: str, password_hash: str) -> None:
        row = self._get_row(username)
        if row is not None:
            row.password_hash = password_hash

    def list_all(self) -> list[User]:
        rows = self._session.scalars(select(UserRow).order_by(UserRow.username)).all()
        return [_to_domain_user(r) for r in rows]

    def count(self) -> int:
        return len(self._session.scalars(select(UserRow.id)).all())

    def _get_row(self, username: str) -> UserRow | None:
        return self._session.scalar(select(UserRow).where(UserRow.username == username))


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, username: str, action: str, details: dict[str, Any] | None = None) -> None:
        self._session.add(
            AuditLogRow(
                username=username,
                action=action,
                details=json.dumps(details, ensure_ascii=False) if details else None,
            )
        )
