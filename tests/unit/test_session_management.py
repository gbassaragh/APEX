"""
Unit tests for session management pattern.

Tests the critical get_db() dependency pattern that ensures:
1. One session per request
2. Automatic commit on success
3. Automatic rollback on error
4. No leaked connections
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from apex.dependencies import get_db


class TestSessionManagement:
    """Test get_db() dependency behavior."""

    def test_get_db_yields_session(self):
        """Test get_db yields a Session instance."""
        with patch("apex.dependencies.SessionLocal") as mock_session_local:
            mock_session = Mock(spec=Session)
            mock_session_local.return_value = mock_session

            # Use generator
            gen = get_db()
            session = next(gen)

            assert session == mock_session
            mock_session_local.assert_called_once()

    def test_get_db_commits_on_success(self):
        """Test session commits when no exception occurs."""
        with patch("apex.dependencies.SessionLocal") as mock_session_local:
            mock_session = Mock(spec=Session)
            mock_session_local.return_value = mock_session

            # Simulate successful execution
            gen = get_db()
            next(gen)
            try:
                gen.send(None)  # Complete generator normally
            except StopIteration:
                pass

            # Should commit and close
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_get_db_rollback_on_exception(self):
        """Test session rolls back when exception occurs."""
        with patch("apex.dependencies.SessionLocal") as mock_session_local:
            mock_session = Mock(spec=Session)
            mock_session_local.return_value = mock_session

            gen = get_db()
            next(gen)

            # Simulate exception
            with pytest.raises(ValueError):
                gen.throw(ValueError("Test error"))

            # Should rollback and close
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
            # Should NOT commit on error
            mock_session.commit.assert_not_called()

    def test_get_db_always_closes_session(self):
        """Test session always closes regardless of outcome."""
        with patch("apex.dependencies.SessionLocal") as mock_session_local:
            mock_session = Mock(spec=Session)
            mock_session_local.return_value = mock_session

            # Test successful path
            gen = get_db()
            next(gen)
            try:
                gen.send(None)
            except StopIteration:
                pass

            mock_session.close.assert_called_once()

            # Reset mock
            mock_session.reset_mock()

            # Test exception path
            gen = get_db()
            next(gen)
            try:
                gen.throw(RuntimeError("Test error"))
            except RuntimeError:
                pass

            mock_session.close.assert_called_once()

    def test_get_db_logs_transaction_failure(self):
        """Test transaction failures are logged."""
        with patch("apex.dependencies.SessionLocal") as mock_session_local:
            with patch("apex.dependencies.logger") as mock_logger:
                mock_session = Mock(spec=Session)
                mock_session_local.return_value = mock_session

                gen = get_db()
                next(gen)

                # Simulate exception
                test_error = RuntimeError("Database error")
                try:
                    gen.throw(test_error)
                except RuntimeError:
                    pass

                # Should log the error
                mock_logger.error.assert_called_once()
                assert "Database transaction failed" in str(mock_logger.error.call_args)

    def test_get_db_reraises_exceptions(self):
        """Test exceptions are re-raised after rollback."""
        with patch("apex.dependencies.SessionLocal") as mock_session_local:
            mock_session = Mock(spec=Session)
            mock_session_local.return_value = mock_session

            gen = get_db()
            next(gen)

            # Exception should be re-raised
            with pytest.raises(ValueError, match="Test error"):
                gen.throw(ValueError("Test error"))


class TestSessionIntegration:
    """Integration tests for session pattern with FastAPI."""

    @pytest.fixture
    def mock_fastapi_dependency(self):
        """Mock FastAPI dependency injection."""
        with patch("apex.dependencies.SessionLocal") as mock_session_local:
            mock_session = Mock(spec=Session)
            mock_session_local.return_value = mock_session
            yield mock_session

    def test_fastapi_request_lifecycle_success(self, mock_fastapi_dependency):
        """Simulate successful FastAPI request lifecycle."""
        # FastAPI dependency injection calls get_db
        gen = get_db()
        session = next(gen)

        assert session == mock_fastapi_dependency

        # Simulate successful request completion
        try:
            gen.send(None)
        except StopIteration:
            pass

        # Verify correct lifecycle
        mock_fastapi_dependency.commit.assert_called_once()
        mock_fastapi_dependency.rollback.assert_not_called()
        mock_fastapi_dependency.close.assert_called_once()

    def test_fastapi_request_lifecycle_error(self, mock_fastapi_dependency):
        """Simulate FastAPI request with error."""
        gen = get_db()
        session = next(gen)

        assert session == mock_fastapi_dependency

        # Simulate request error
        try:
            gen.throw(Exception("Request failed"))
        except Exception:
            pass

        # Verify error handling lifecycle
        mock_fastapi_dependency.commit.assert_not_called()
        mock_fastapi_dependency.rollback.assert_called_once()
        mock_fastapi_dependency.close.assert_called_once()


class TestSessionIsolation:
    """Test session isolation between requests."""

    def test_multiple_get_db_calls_create_separate_sessions(self):
        """Test each get_db() call creates a new session."""
        with patch("apex.dependencies.SessionLocal") as mock_session_local:
            mock_session1 = Mock(spec=Session)
            mock_session2 = Mock(spec=Session)
            mock_session_local.side_effect = [mock_session1, mock_session2]

            # First call
            gen1 = get_db()
            session1 = next(gen1)

            # Second call
            gen2 = get_db()
            session2 = next(gen2)

            # Should be different sessions
            assert session1 != session2
            assert mock_session_local.call_count == 2

    def test_session_not_reused_after_close(self):
        """Test sessions are not reused after closing."""
        with patch("apex.dependencies.SessionLocal") as mock_session_local:
            mock_session = Mock(spec=Session)
            mock_session_local.return_value = mock_session

            # Complete first request
            gen1 = get_db()
            next(gen1)
            try:
                gen1.send(None)
            except StopIteration:
                pass

            mock_session.close.assert_called_once()

            # Second request gets new session
            mock_session_local.return_value = Mock(spec=Session)
            gen2 = get_db()
            session2 = next(gen2)

            assert mock_session_local.call_count == 2
