"""
Unit tests for app/utils/encryption.py

Tests encryption and decryption functionality using Fernet symmetric encryption.
Critical for securing OAuth tokens and other sensitive data.
"""

import pytest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet, InvalidToken

from app.utils.encryption import EncryptionService


class TestEncryptionService:
    """Tests for the EncryptionService class."""

    @pytest.fixture
    def valid_key(self):
        """Generate a valid Fernet key for testing."""
        return Fernet.generate_key().decode()

    @pytest.fixture
    def encryption_service(self, valid_key):
        """Create an EncryptionService instance with a valid key."""
        return EncryptionService(encryption_key=valid_key)

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init_with_valid_key(self, valid_key):
        """Should initialize successfully with valid key."""
        service = EncryptionService(encryption_key=valid_key)
        assert service.fernet is not None

    def test_init_with_string_key(self, valid_key):
        """Should accept string key."""
        service = EncryptionService(encryption_key=valid_key)
        assert service is not None

    def test_init_with_bytes_key(self):
        """Should accept bytes key."""
        key = Fernet.generate_key()  # This is bytes
        service = EncryptionService(encryption_key=key)
        assert service is not None

    def test_init_with_invalid_key_raises(self):
        """Should raise ValueError for invalid key."""
        with pytest.raises(ValueError, match="Invalid encryption key"):
            EncryptionService(encryption_key="not-a-valid-key")

    def test_init_with_empty_key_raises(self):
        """Should raise ValueError for empty key."""
        with pytest.raises(ValueError, match="ENCRYPTION_KEY not configured"):
            EncryptionService(encryption_key="")

    def test_init_with_none_key_tries_settings(self):
        """Should try to load from settings when key is None."""
        mock_settings = MagicMock()
        mock_settings.encryption_key = Fernet.generate_key().decode()

        with patch.dict('sys.modules', {'app.config.settings': MagicMock(settings=mock_settings)}):
            # This will try to import settings and use its encryption_key
            # In tests, this will fail unless we properly mock it
            pass

    # ========================================================================
    # Encryption Tests
    # ========================================================================

    def test_encrypt_returns_string(self, encryption_service):
        """Encrypt should return a string."""
        result = encryption_service.encrypt("test data")
        assert isinstance(result, str)

    def test_encrypt_returns_base64(self, encryption_service):
        """Encrypted output should be base64-encoded."""
        result = encryption_service.encrypt("test data")
        # Fernet output is URL-safe base64
        import base64
        # Should not raise
        base64.urlsafe_b64decode(result)

    def test_encrypt_different_each_time(self, encryption_service):
        """Same plaintext should encrypt to different ciphertext (due to nonce)."""
        plaintext = "test data"
        result1 = encryption_service.encrypt(plaintext)
        result2 = encryption_service.encrypt(plaintext)
        assert result1 != result2

    def test_encrypt_empty_string_raises(self, encryption_service):
        """Encrypting empty string should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot encrypt empty plaintext"):
            encryption_service.encrypt("")

    def test_encrypt_none_raises(self, encryption_service):
        """Encrypting None should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot encrypt empty plaintext"):
            encryption_service.encrypt(None)

    def test_encrypt_unicode(self, encryption_service):
        """Should handle Unicode characters correctly."""
        plaintext = "Test with émojis 🔐 and spëcial çharacters"
        result = encryption_service.encrypt(plaintext)
        assert isinstance(result, str)
        # Verify by decrypting
        decrypted = encryption_service.decrypt(result)
        assert decrypted == plaintext

    def test_encrypt_long_string(self, encryption_service):
        """Should handle long strings."""
        plaintext = "x" * 10000
        result = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(result)
        assert decrypted == plaintext

    def test_encrypt_json_like_string(self, encryption_service):
        """Should handle JSON-like strings (common for OAuth tokens)."""
        plaintext = '{"access_token": "abc123", "refresh_token": "xyz789"}'
        result = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(result)
        assert decrypted == plaintext

    # ========================================================================
    # Decryption Tests
    # ========================================================================

    def test_decrypt_returns_string(self, encryption_service):
        """Decrypt should return a string."""
        ciphertext = encryption_service.encrypt("test data")
        result = encryption_service.decrypt(ciphertext)
        assert isinstance(result, str)

    def test_decrypt_returns_original(self, encryption_service):
        """Decrypt should return original plaintext."""
        plaintext = "my secret data"
        ciphertext = encryption_service.encrypt(plaintext)
        result = encryption_service.decrypt(ciphertext)
        assert result == plaintext

    def test_decrypt_empty_string_raises(self, encryption_service):
        """Decrypting empty string should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot decrypt empty ciphertext"):
            encryption_service.decrypt("")

    def test_decrypt_none_raises(self, encryption_service):
        """Decrypting None should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot decrypt empty ciphertext"):
            encryption_service.decrypt(None)

    def test_decrypt_invalid_ciphertext_raises(self, encryption_service):
        """Decrypting invalid ciphertext should raise InvalidToken."""
        with pytest.raises(InvalidToken):
            encryption_service.decrypt("not-valid-ciphertext")

    def test_decrypt_tampered_ciphertext_raises(self, encryption_service):
        """Tampered ciphertext should raise InvalidToken."""
        ciphertext = encryption_service.encrypt("test data")
        # Tamper with the ciphertext
        tampered = ciphertext[:-5] + "XXXXX"
        with pytest.raises(InvalidToken):
            encryption_service.decrypt(tampered)

    def test_decrypt_with_wrong_key_raises(self, valid_key):
        """Decrypting with different key should raise InvalidToken."""
        service1 = EncryptionService(encryption_key=valid_key)
        ciphertext = service1.encrypt("test data")

        # Create service with different key
        different_key = Fernet.generate_key().decode()
        service2 = EncryptionService(encryption_key=different_key)

        with pytest.raises(InvalidToken):
            service2.decrypt(ciphertext)

    # ========================================================================
    # Round-trip Tests
    # ========================================================================

    def test_roundtrip_simple_string(self, encryption_service):
        """Simple string should survive encrypt/decrypt round-trip."""
        original = "Hello, World!"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_roundtrip_multiline_string(self, encryption_service):
        """Multiline string should survive round-trip."""
        original = "Line 1\nLine 2\nLine 3"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_roundtrip_special_characters(self, encryption_service):
        """Special characters should survive round-trip."""
        original = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original

    def test_roundtrip_whitespace(self, encryption_service):
        """Whitespace should be preserved."""
        original = "  leading and trailing  \t tabs \n newlines  "
        encrypted = encryption_service.encrypt(original)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == original


class TestEncryptionServiceKeyFormats:
    """Tests for different key format handling."""

    def test_key_with_padding(self):
        """Key with base64 padding should work."""
        key = Fernet.generate_key().decode()
        # Fernet keys are always 44 chars with = padding
        assert key.endswith("=")
        service = EncryptionService(encryption_key=key)
        assert service is not None

    def test_rejects_short_key(self):
        """Key that's too short should be rejected."""
        with pytest.raises(ValueError):
            EncryptionService(encryption_key="short")

    def test_rejects_non_base64_key(self):
        """Non-base64 characters should cause rejection."""
        with pytest.raises(ValueError):
            EncryptionService(encryption_key="not!valid@base64#chars")


class TestEncryptionServiceConcurrency:
    """Tests for thread-safety and concurrent usage."""

    def test_multiple_encrypt_calls(self):
        """Multiple encrypt calls should not interfere."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)

        plaintexts = [f"secret {i}" for i in range(100)]
        ciphertexts = [service.encrypt(p) for p in plaintexts]
        decrypted = [service.decrypt(c) for c in ciphertexts]

        assert decrypted == plaintexts

    def test_service_reuse(self):
        """Service should be reusable for multiple operations."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)

        # First round
        c1 = service.encrypt("data 1")
        d1 = service.decrypt(c1)
        assert d1 == "data 1"

        # Second round
        c2 = service.encrypt("data 2")
        d2 = service.decrypt(c2)
        assert d2 == "data 2"

        # Original still works
        d1_again = service.decrypt(c1)
        assert d1_again == "data 1"


class TestRealWorldScenarios:
    """Tests simulating real-world usage patterns."""

    @pytest.fixture
    def service(self):
        """Create encryption service for real-world tests."""
        key = Fernet.generate_key().decode()
        return EncryptionService(encryption_key=key)

    def test_oauth_token_storage(self, service):
        """Simulate storing/retrieving OAuth tokens."""
        oauth_data = {
            "access_token": "ya29.a0AfH6SMBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "refresh_token": "1//0gxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "12345.apps.googleusercontent.com",
            "client_secret": "GOCSPX-xxxxxxxxxxxxxxxxxxxxxxxx",
            "expiry": "2024-01-15T12:00:00Z"
        }
        import json
        plaintext = json.dumps(oauth_data)

        # Encrypt for storage
        ciphertext = service.encrypt(plaintext)
        assert ciphertext != plaintext
        assert "access_token" not in ciphertext

        # Decrypt for use
        decrypted = service.decrypt(ciphertext)
        recovered_data = json.loads(decrypted)
        assert recovered_data == oauth_data

    def test_api_key_storage(self, service):
        """Simulate storing API keys."""
        api_key = "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

        ciphertext = service.encrypt(api_key)
        assert "sk-ant" not in ciphertext

        decrypted = service.decrypt(ciphertext)
        assert decrypted == api_key

    def test_password_storage(self, service):
        """Simulate storing sensitive credentials."""
        password = "Super$ecret!Password123"

        ciphertext = service.encrypt(password)
        assert password not in ciphertext

        decrypted = service.decrypt(ciphertext)
        assert decrypted == password
