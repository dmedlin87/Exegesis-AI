"""Detailed unit tests for security adapter edge cases."""

import time
from unittest.mock import MagicMock, patch

import pytest
import jwt
from fastapi import Request, HTTPException

from theo.infrastructure.api.app.adapters.security import FastAPIPrincipalResolver
from theo.application.facades.settings import Settings

class TestSecurityAdapterDetailed:

    @pytest.fixture
    def resolver(self):
        return FastAPIPrincipalResolver()

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock(spec=Settings)
        settings.api_keys = ["valid-key"]
        settings.auth_jwt_secret = "secret"
        settings.auth_jwt_algorithms = ["HS256"]
        settings.auth_jwt_audience = None
        settings.auth_jwt_issuer = None
        settings.has_auth_jwt_credentials.return_value = True
        settings.load_auth_jwt_public_key.return_value = None
        return settings

    def test_decode_jwt_missing_alg(self, resolver, mock_settings):
        """JWT missing algorithm header should raise 403 (wrapped InvalidTokenError)."""
        token = "invalid.token.part"

        with patch("jwt.get_unverified_header", return_value={}): # No alg
             with pytest.raises(HTTPException) as exc:
                 resolver._decode_jwt(token, mock_settings)
             assert exc.value.status_code == 403
             assert "Invalid bearer token" in exc.value.detail

    def test_decode_jwt_unsupported_alg(self, resolver, mock_settings):
        """JWT with algorithm not in settings should be rejected with 403."""
        with patch("jwt.get_unverified_header", return_value={"alg": "RS256"}):
             with pytest.raises(HTTPException) as exc:
                 resolver._decode_jwt("token", mock_settings)
             assert exc.value.status_code == 403
             assert "Invalid bearer token" in exc.value.detail

    def test_decode_jwt_expired(self, resolver, mock_settings):
        """Expired token should raise 401."""
        # We mock jwt.decode to raise ExpiredSignatureError
        with patch("jwt.decode", side_effect=jwt.ExpiredSignatureError("Expired")):
            with patch("jwt.get_unverified_header", return_value={"alg": "HS256"}):
                with pytest.raises(HTTPException) as exc:
                    resolver._decode_jwt("token", mock_settings)
                assert exc.value.status_code == 401
                assert "Token has expired" in exc.value.detail

    def test_decode_jwt_invalid_token(self, resolver, mock_settings):
        """Malformed token should raise 403."""
        with patch("jwt.decode", side_effect=jwt.InvalidTokenError("Bad token")):
            with patch("jwt.get_unverified_header", return_value={"alg": "HS256"}):
                with pytest.raises(HTTPException) as exc:
                    resolver._decode_jwt("token", mock_settings)
                assert exc.value.status_code == 403
                assert "Invalid bearer token" in exc.value.detail

    def test_settings_cache_refresh(self, resolver):
        """Verify settings cache refresh logic respects interval and lock."""
        with patch("theo.infrastructure.api.app.adapters.security.get_settings") as mock_get_settings:
            # First call
            resolver._refresh_settings_cache_if_stale()
            assert mock_get_settings.cache_clear.called
            mock_get_settings.cache_clear.reset_mock()

            # Immediate second call (within interval) -> should NOT clear
            resolver._refresh_settings_cache_if_stale()
            assert not mock_get_settings.cache_clear.called

            # Fast forward time
            resolver._settings_refreshed_at -= 100 # Force stale
            resolver._refresh_settings_cache_if_stale()
            assert mock_get_settings.cache_clear.called

    def test_resolve_rejects_unsupported_scheme(self, resolver, mock_settings):
        """Authorization header with non-Bearer scheme should be rejected."""
        with pytest.raises(HTTPException) as exc:
            resolver._principal_from_authorization("Basic user:pass", mock_settings)
        assert exc.value.status_code == 401
        assert "Unsupported authorization scheme" in exc.value.detail

    def test_resolve_rejects_missing_credentials(self, resolver, mock_settings):
        """Authorization header "Bearer " with no token."""
        with pytest.raises(HTTPException) as exc:
            resolver._principal_from_authorization("Bearer ", mock_settings)
        assert exc.value.status_code == 401
        assert "Missing bearer token" in exc.value.detail

    def test_resolve_handles_api_key_in_auth_header(self, resolver, mock_settings):
        """Authorization header without scheme is treated as API key if not 3 parts."""
        # If credentials.count(".") != 2, it calls _authenticate_api_key
        # "Bearer my-api-key" -> scheme="Bearer", credentials="my-api-key"
        # But wait, _principal_from_authorization expects "Bearer <cred>"

        # If I send "Bearer my-api-key", scheme is Bearer.
        # credentials is "my-api-key". count('.') is 0.
        # Calls _authenticate_api_key("my-api-key").

        principal = resolver._principal_from_authorization("Bearer valid-key", mock_settings)
        assert principal["method"] == "api_key"
        assert principal["subject"] == "valid-key"

    def test_resolve_scopes_parsing(self, resolver, mock_settings):
        """Verify scopes are parsed from string or list."""
        with patch("jwt.get_unverified_header", return_value={"alg": "HS256"}), \
             patch("jwt.decode") as mock_decode:

            # Case 1: space-separated string
            mock_decode.return_value = {"sub": "user", "scopes": "read write"}
            principal = resolver._decode_jwt("token", mock_settings)
            assert principal["scopes"] == ["read", "write"]

            # Case 2: list
            mock_decode.return_value = {"sub": "user", "scopes": ["admin"]}
            principal = resolver._decode_jwt("token", mock_settings)
            assert principal["scopes"] == ["admin"]

            # Case 3: None/Missing
            mock_decode.return_value = {"sub": "user"}
            principal = resolver._decode_jwt("token", mock_settings)
            assert principal["scopes"] == []

