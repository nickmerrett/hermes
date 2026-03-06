"""
Unit tests for core/database.py

Covers:
- get_db() rolls back the session when a request handler raises
- get_db() always closes the session (even on exception)
- pool_pre_ping is enabled on the engine
"""

import os
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")

from cryptography.fernet import Fernet
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())


class TestGetDbSessionHandling:
    """get_db() must rollback on exception and always close."""

    def _make_mock_session(self):
        session = MagicMock()
        return session

    def _call_get_db(self, session, raise_exc=None):
        """Drive the get_db generator the same way FastAPI does."""
        from app.core.database import get_db

        mock_session_local = MagicMock(return_value=session)

        with patch("app.core.database._get_engine_and_session", return_value=(MagicMock(), mock_session_local)):
            gen = get_db()
            db = next(gen)  # FastAPI calls next() to get the session
            assert db is session

            if raise_exc:
                try:
                    gen.throw(raise_exc)
                except type(raise_exc):
                    pass
            else:
                try:
                    next(gen)
                except StopIteration:
                    pass

    def test_session_closed_on_success(self):
        """Session must be closed after a normal (no-exception) request."""
        session = self._make_mock_session()
        self._call_get_db(session)
        session.close.assert_called_once()

    def test_session_rolled_back_on_exception(self):
        """Session must be rolled back when the request handler raises."""
        session = self._make_mock_session()
        self._call_get_db(session, raise_exc=RuntimeError("handler error"))
        session.rollback.assert_called_once()

    def test_session_closed_on_exception(self):
        """Session must be closed even when the request handler raises."""
        session = self._make_mock_session()
        self._call_get_db(session, raise_exc=RuntimeError("handler error"))
        session.close.assert_called_once()

    def test_no_rollback_on_success(self):
        """Session must NOT be rolled back when there is no exception."""
        session = self._make_mock_session()
        self._call_get_db(session)
        session.rollback.assert_not_called()

    def test_exception_is_reraised(self):
        """The original exception must propagate out of get_db()."""
        from app.core.database import get_db

        session = self._make_mock_session()
        mock_session_local = MagicMock(return_value=session)

        with patch("app.core.database._get_engine_and_session", return_value=(MagicMock(), mock_session_local)):
            gen = get_db()
            next(gen)
            with pytest.raises(ValueError, match="boom"):
                gen.throw(ValueError("boom"))


class TestEngineConfiguration:
    """The SQLAlchemy engine must be configured for resilience."""

    def test_pool_pre_ping_enabled(self):
        """Engine must have pool_pre_ping=True to detect stale connections."""
        with patch("app.core.database.os.environ.get", return_value=None), \
             patch("app.core.database.os.makedirs"), \
             patch("app.core.database.create_engine") as mock_create_engine, \
             patch("app.core.database.settings") as mock_settings:

            mock_settings.database_url = "sqlite:///test.db"
            mock_settings.database_path = "/tmp/test.db"
            mock_settings.sql_echo = False
            mock_create_engine.return_value = MagicMock()

            from app.core.database import get_engine
            get_engine()

            _, kwargs = mock_create_engine.call_args
            assert kwargs.get("pool_pre_ping") is True, (
                "pool_pre_ping must be True so stale connections are detected before use"
            )
