# Stage 3 preliminary implementation: DPAPI helper

Added `kivo_security.py` as an isolated Windows DPAPI helper using user-scope CryptProtectData/CryptUnprotectData. It emits values tagged `dpapi:v1:` and does not use the machine-wide flag.

## Important integration boundary
This helper is **not yet wired into Config.ini or AI request code**. Existing credentials remain plaintext until a tested migration and integration is implemented. This is intentional: a premature storage-format change could lock users out of their existing AI configuration.

## Test plan
- Run the portable unit suite on non-Windows (expected: format validation tests pass; Windows round trip is skipped).
- Run the round-trip test on Windows under the same user account.
- Verify ciphertext cannot be decrypted under another Windows account.
- Test legacy plaintext migration, backups, rollback, corrupted ciphertext, and app startup recovery before integration.

## Data portability warning
DPAPI user-scope ciphertext is generally tied to the Windows user profile and machine context. Users should not expect encrypted keys to transfer by copying Config.ini to another Windows machine/user. A future migration must offer clear recovery/export guidance and never overwrite the only copy of a key without successful encryption verification.
