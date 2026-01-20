"""
Encryption utilities for securely storing sensitive data like OAuth tokens.

Uses Fernet (symmetric encryption) from the cryptography library.
"""

import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.

    Uses Fernet symmetric encryption with a key from environment variable.
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption service.

        Args:
            encryption_key: Base64-encoded Fernet key. If None, will try to import from settings.

        Raises:
            ValueError: If encryption_key is not provided or invalid.
        """
        if encryption_key is None:
            # Import here to avoid circular dependency
            try:
                from app.config.settings import settings
                encryption_key = settings.encryption_key
            except Exception as e:
                raise ValueError(f"Could not load encryption_key from settings: {e}")

        if not encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY not configured. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        try:
            self.fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded ciphertext as a string

        Raises:
            ValueError: If plaintext is empty or None
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty plaintext")

        try:
            ciphertext_bytes = self.fernet.encrypt(plaintext.encode('utf-8'))
            return ciphertext_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a string.

        Args:
            ciphertext: Base64-encoded ciphertext string

        Returns:
            Decrypted plaintext string

        Raises:
            ValueError: If ciphertext is empty or None
            InvalidToken: If ciphertext is invalid or key doesn't match
        """
        if not ciphertext:
            raise ValueError("Cannot decrypt empty ciphertext")

        try:
            plaintext_bytes = self.fernet.decrypt(ciphertext.encode('utf-8'))
            return plaintext_bytes.decode('utf-8')
        except InvalidToken:
            logger.error("Decryption failed: Invalid token or wrong key")
            raise
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise


# Global instance - lazily initialized on first use
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get the global encryption service instance.

    Returns:
        EncryptionService instance
    """
    global _encryption_service

    if _encryption_service is None:
        _encryption_service = EncryptionService()

    return _encryption_service


# Convenience functions for direct use
def encrypt(plaintext: str) -> str:
    """Encrypt a string using the global encryption service."""
    return get_encryption_service().encrypt(plaintext)


def decrypt(ciphertext: str) -> str:
    """Decrypt a string using the global encryption service."""
    return get_encryption_service().decrypt(ciphertext)
