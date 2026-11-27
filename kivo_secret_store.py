"""Compatibility layer for migrating KIVO AI keys to DPAPI.

This module is deliberately not wired into main.py yet. It defines the migration
contract and can be tested with an injected protector on non-Windows platforms.
"""
from __future__ import annotations

from typing import Callable

_MARKER = "dpapi:v1:"


def read_secret(value: str, decrypt: Callable[[str], str]) -> str:
    """Read legacy plaintext or decrypt marked values; never pass ciphertext as a key."""
    value = value or ""
    if value.startswith(_MARKER):
        return decrypt(value)
    return value


def write_secret(value: str, encrypt: Callable[[str], str]) -> str:
    """Encrypt non-empty plaintext; leave empty values empty and marked values untouched."""
    value = value or ""
    if not value:
        return ""
    if value.startswith(_MARKER):
        return value
    result = encrypt(value)
    if not isinstance(result, str) or not result.startswith(_MARKER):
        raise ValueError("encryptor did not return a DPAPI-marked value")
    return result


def is_protected(value: str) -> bool:
    return bool(value) and value.startswith(_MARKER)
