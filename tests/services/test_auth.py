"""Tests for password hashing and the AuthService use cases."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from crossdock.domain.models import Role
from crossdock.services.auth import AuthService, hash_password, verify_password
from crossdock.storage.repositories import UserRepository
from crossdock.storage.tables import AuditLogRow, UserRow


class TestPasswordHashing:
    def test_hash_differs_from_plaintext_and_verifies(self) -> None:
        hashed = hash_password("tajne-haslo")
        assert hashed != "tajne-haslo"
        assert verify_password(hashed, "tajne-haslo")

    def test_wrong_password_fails_verification(self) -> None:
        hashed = hash_password("tajne-haslo")
        assert not verify_password(hashed, "inne-haslo")

    def test_garbage_hash_fails_gracefully(self) -> None:
        assert not verify_password("not-a-hash", "cokolwiek")

    def test_same_password_produces_different_hashes(self) -> None:
        assert hash_password("abc") != hash_password("abc")  # random salt


class TestAuthenticate:
    def test_valid_credentials_return_user(self, db_session: Session) -> None:
        service = AuthService(db_session)
        service.create_user("anna", "haslo123", Role.DISPATCHER)
        user = service.authenticate("anna", "haslo123")
        assert user is not None
        assert user.username == "anna"
        assert user.role == Role.DISPATCHER

    def test_wrong_password_is_rejected(self, db_session: Session) -> None:
        service = AuthService(db_session)
        service.create_user("anna", "haslo123", Role.DISPATCHER)
        assert service.authenticate("anna", "zle-haslo") is None

    def test_unknown_username_is_rejected(self, db_session: Session) -> None:
        service = AuthService(db_session)
        assert service.authenticate("nikt", "haslo123") is None

    def test_inactive_account_is_rejected(self, db_session: Session) -> None:
        service = AuthService(db_session)
        service.create_user("anna", "haslo123", Role.DISPATCHER)
        row = db_session.scalar(select(UserRow).where(UserRow.username == "anna"))
        assert row is not None
        row.is_active = False
        assert service.authenticate("anna", "haslo123") is None

    def test_successful_login_is_audited(self, db_session: Session) -> None:
        service = AuthService(db_session)
        service.create_user("anna", "haslo123", Role.DISPATCHER)
        service.authenticate("anna", "haslo123")
        actions = db_session.scalars(select(AuditLogRow.action)).all()
        assert "login" in actions


class TestCreateUser:
    def test_duplicate_username_is_rejected(self, db_session: Session) -> None:
        service = AuthService(db_session)
        service.create_user("anna", "haslo123", Role.DISPATCHER)
        try:
            service.create_user("anna", "inne", Role.VIEWER)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for duplicate username")

    def test_password_is_stored_hashed(self, db_session: Session) -> None:
        service = AuthService(db_session)
        service.create_user("anna", "haslo123", Role.DISPATCHER)
        stored = UserRepository(db_session).get_password_hash("anna")
        assert stored is not None
        assert "haslo123" not in stored


class TestSeedAdmin:
    def test_seed_creates_exactly_one_admin(self, db_session: Session) -> None:
        service = AuthService(db_session)
        assert service.seed_admin("startowe-haslo") is True
        users = UserRepository(db_session).list_all()
        assert len(users) == 1
        assert users[0].username == "admin"
        assert users[0].role == Role.ADMIN

    def test_seed_is_idempotent(self, db_session: Session) -> None:
        service = AuthService(db_session)
        assert service.seed_admin("startowe-haslo") is True
        assert service.seed_admin("startowe-haslo") is False
        assert UserRepository(db_session).count() == 1

    def test_seed_skipped_when_any_user_exists(self, db_session: Session) -> None:
        service = AuthService(db_session)
        service.create_user("anna", "haslo123", Role.DISPATCHER)
        assert service.seed_admin("startowe-haslo") is False
