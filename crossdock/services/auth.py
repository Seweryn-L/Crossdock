"""Authentication use cases: password hashing, login, account seeding.

Passwords are hashed with argon2 (argon2-cffi defaults). Failed logins
never reveal whether the username exists or the account is inactive.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy.orm import Session

from crossdock.domain.models import Role, User
from crossdock.storage.repositories import AuditLogRepository, UserRepository

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


class AuthService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._audit = AuditLogRepository(session)

    def authenticate(self, username: str, password: str) -> User | None:
        """Return the user on success, ``None`` on any failure.

        Unknown username, wrong password and inactive account are all
        indistinguishable to the caller.
        """
        user = self._users.get_by_username(username)
        password_hash = self._users.get_password_hash(username)
        if user is None or password_hash is None:
            return None
        if not verify_password(password_hash, password):
            return None
        if not user.is_active:
            return None
        if _hasher.check_needs_rehash(password_hash):
            self._users.update_password_hash(username, hash_password(password))
        self._audit.record(username, "login")
        return user

    def create_user(self, username: str, password: str, role: Role) -> User:
        if self._users.get_by_username(username) is not None:
            raise ValueError(f"User {username!r} already exists.")
        user = self._users.add(username, hash_password(password), role)
        self._audit.record(username, "user_created", {"role": role.value})
        return user

    def seed_admin(self, admin_password: str) -> bool:
        """Create the initial admin account when the users table is empty.

        Returns ``True`` when the admin was created, ``False`` when users
        already exist (idempotent — safe to call on every startup).
        """
        if self._users.count() > 0:
            return False
        self._users.add("admin", hash_password(admin_password), Role.ADMIN)
        self._audit.record("admin", "admin_seeded")
        return True
