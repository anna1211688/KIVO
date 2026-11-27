"""Small, explicit helpers for AI key migration, kept isolated pending main.py integration."""
from __future__ import annotations

from kivo_secret_store import read_secret, write_secret
from kivo_security import protect_secret, unprotect_secret


def decode_config_key(value: str) -> str:
    """Return plaintext key for runtime use; decrypt marked values on Windows."""
    return read_secret(value, unprotect_secret)


def encode_config_key(value: str) -> str:
    """Protect non-empty keys on explicit config save."""
    return write_secret(value, protect_secret)


def migrate_key_value(value: str) -> str:
    """Idempotently protect a legacy key; caller must save transactionally."""
    return encode_config_key(value)
