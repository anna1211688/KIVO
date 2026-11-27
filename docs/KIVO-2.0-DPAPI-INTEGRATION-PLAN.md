# KIVO DPAPI integration plan (Stage 3.1)

## Decision: keep main.py unchanged in this commit

The AI settings UI writes four provider-specific keys and the active-service mirror (ApiKey) in _save_ai_settings. The accessor _ai_cfg currently returns provider-specific keys with an active-service legacy mirror fallback. Any integration must encrypt all provider-specific keys and the mirror, while decrypting at read time.

## Required migration behavior

- Recognize the dpapi:v1: marker and decrypt only through the Windows-user DPAPI helper.
- Plaintext legacy keys remain readable during migration.
- Migration should be performed only when settings are explicitly saved, not as a startup side effect.
- On save, encrypt every non-empty provider key and the generic mirror. Empty keys remain empty; avoid creating empty ciphertext markers.
- If decryption fails, do not silently treat ciphertext as a plaintext API key. Surface a clear error and preserve the existing file rather than overwriting it.
- Ensure API key values are never included in crash-log messages, diagnostics, exception text, or telemetry.
- A backup/restore and atomic write strategy is required before enabling migration.
- Non-Windows development environments should retain tests for marker recognition and mock DPAPI behavior, but actual encryption/decryption must be Windows-tested.

## Validation matrix before integration

| Scenario | Expected |
|---|---|
| Existing plaintext provider keys | Read normally; encrypted upon explicit successful save |
| Existing generic ApiKey only | Current service fallback remains intact |
| Multiple provider keys | Each remains isolated; encrypt/decrypt independently |
| Corrupt ciphertext | Save is blocked; file is preserved |
| Empty key | Stored empty, not ciphertext |
| Current service mirror | Encrypted, not duplicated as plaintext |
| Windows current user | Round-trip succeeds |
| Different Windows user | Decryption fails safely |
| Interrupted save / disk-full | Previous config preserved |
| Legacy backup | Restore remains readable and migration can retry |

## Risks still open

The current save routine rewrites Config.ini and can normalize scalar values. Migration must be integrated with that routine's failure semantics, tested on Windows, and audited for any other UI paths that write AI keys. No claims of runtime validation are made here.
