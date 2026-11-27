"""Windows DPAPI helpers for KIVO secret storage (Stage 3).

This module is intentionally standalone during the staged migration. Integration
into Config.ini is deferred until compatibility and Windows runtime tests exist.
"""
from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes

_PREFIX = "dpapi:v1:"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buf = ctypes.create_string_buffer(data)
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf


def protect_secret(secret: str) -> str:
    """Encrypt secret for the current Windows user; raises on unsupported OS."""
    if os.name != "nt":
        raise OSError("DPAPI secret protection is only available on Windows")
    if not isinstance(secret, str):
        raise TypeError("secret must be str")
    if not secret:
        return _PREFIX
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt.CryptProtectData.argtypes = [ctypes.POINTER(_Blob), wintypes.LPCWSTR,
        ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(_Blob)]
    crypt.CryptProtectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    src, src_buf = _blob(secret.encode("utf-8"))
    out = _Blob()
    if not crypt.CryptProtectData(ctypes.byref(src), "KIVO", None, None, None, 0, ctypes.byref(out)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        encrypted = ctypes.string_at(out.pbData, out.cbData)
        return _PREFIX + base64.b64encode(encrypted).decode("ascii")
    finally:
        kernel.LocalFree(out.pbData)


def unprotect_secret(value: str) -> str:
    """Decrypt a DPAPI-prefixed value for the current Windows user."""
    if not value.startswith(_PREFIX):
        raise ValueError("value is not a DPAPI:v1 secret")
    encoded = value[len(_PREFIX):]
    if not encoded:
        return ""
    if os.name != "nt":
        raise OSError("DPAPI secret decryption is only available on Windows")
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(_Blob), ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(_Blob)]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    src, src_buf = _blob(base64.b64decode(encoded, validate=True))
    out = _Blob()
    if not crypt.CryptUnprotectData(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(out.pbData, out.cbData).decode("utf-8")
    finally:
        kernel.LocalFree(out.pbData)
