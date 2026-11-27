# KIVO 2.0 — Stage 2: Test & Security Baseline

Date: 2026-11-27  
Branch: `kivo-2.0-audit`  
Scope: static review of configuration persistence, AI credentials, HTTP calls, updater verification, and media downloader. No Windows runtime validation was performed.

## Findings (reviewed excerpts)

### Configuration storage
- The app writes configuration through an atomic-write helper when creating the config, but updates existing INI files by rewriting matching lines. Validate crash recovery and encoding round-trips on Windows before relying on this path.
- API credentials are stored in plaintext in local `Config.ini`. This is a deliberate compatibility choice but is not secure storage. Users should protect the file and avoid sharing it or diagnostic bundles.
- Saving config failure is caught and logged; check log sanitization so credentials or request payloads are not leaked.

### AI keys and request handling
- Service-specific keys and the generic active-service key mirror are present. Regression tests guard active-service fallback and URL scheme validation.
- HTTP requests use timeouts; error detail is bounded in at least one AI HTTP-error path, but broader exception paths and request logging need review for accidental credential disclosure.
- URL scheme validation permits HTTP as well as HTTPS (needed for some local endpoints); UI should warn users when a remote endpoint is configured without HTTPS.

### Updater
- The reviewed update path requires a signature manifest, compares the installer digest, and verifies a signature using an embedded public key.
- Further testing is required: malformed manifest, oversized response, redirect handling, signature version binding, rollback/downgrade behavior, partial download cleanup, installer execution flags, and end-to-end Windows verification.

### Media downloads
- The downloader uses yt-dlp, a socket timeout, retry count, playlist suppression, and title length limits in the output template.
- These are useful baseline controls but not a complete download security boundary. Add tests for user-selected output directories, cookies-from-browser consent, disk-full behavior, cancellation, malicious/unsupported URLs, and error messages. Avoid claiming platform policy compliance; users must have permission to download content.

## Stage 2 tests added
`tests/test_stage2_security_baseline.py` is a static guard suite. It checks source-level presence of several controls; it does **not** prove runtime security or behavior. Run on Python 3.12:

```powershell
python -m unittest discover -s tests -v
```

## Next review/testing backlog
1. Secret/log scrub audit and config backup/restore/permissions.
2. HTTP response size bounds and redirect policy; retry behavior where appropriate.
3. Updater manifest/installer size bounds, version anti-rollback, and temporary-file cleanup.
4. yt-dlp cancellation, cookies consent, destination validation and disk-space handling.
5. Windows smoke tests: clean install, upgrade, uninstall, config preservation, AI request, offline behavior.
6. Add dependency lock file and reproducible release-build verification.

## Status
The checks are source-level assertions. They have not been executed against a local checkout in this review session. CI or a local Windows environment should run them before the branch is considered validated.
