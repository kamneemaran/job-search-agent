"""Encrypt sensitive per-user values (e.g. Gmail app password) before storing in the DB."""
import os
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("jobpilot.crypto")

PREFIX = "enc:"


def _get_key() -> bytes | None:
    """Derive a Fernet key from the APP_PASSWORD_ENCRYPTION_KEY env var."""
    secret = os.environ.get("APP_PASSWORD_ENCRYPTION_KEY", "")
    if not secret:
        logger.warning("APP_PASSWORD_ENCRYPTION_KEY not set — sensitive values stored in plaintext.")
        return None
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_text(plain: str) -> str:
    """Encrypt plaintext. Returns plaintext unchanged if no encryption key is configured."""
    if not plain:
        return plain
    key = _get_key()
    if not key:
        return plain
    try:
        token = Fernet(key).encrypt(plain.encode("utf-8")).decode("utf-8")
        return f"{PREFIX}{token}"
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return plain


def decrypt_text(stored: str) -> str:
    """Decrypt a value previously stored by encrypt_text.

    Handles legacy plaintext values (no prefix) transparently.
    """
    if not stored:
        return stored
    if not stored.startswith(PREFIX):
        return stored
    key = _get_key()
    if not key:
        return stored
    try:
        token = stored[len(PREFIX):]
        return Fernet(key).decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt stored value — key may have changed.")
        return stored
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return stored
