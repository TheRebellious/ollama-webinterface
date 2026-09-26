# Changelog

All notable changes to Ollama Console will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Comprehensive security documentation in README.md
  - HTTPS/TLS configuration guidelines with reverse proxy examples
  - Bearer token hardening recommendations
  - Network isolation and firewall guidance
  - Security audit checklist for production deployment
- Logging and monitoring best practices section
- Health check and resource monitoring recommendations

### Changed
- Updated README.md security section to include detailed TLS/TLS configuration instructions
- Enhanced Firewall section with references to security documentation

---

## [1.0.0] - 2026-09-26

### Added
- **Authentication**: Bearer token middleware for all `/api/*` routes with configurable secrets
- **Rate Limiting**: Thread-safe sliding-window rate limiter with `X-RateLimit-*` and `Retry-After` headers
- **Sensitive Data Redaction**: Automatic log filtering for passwords, tokens, and API keys
- **CORS Headers**: Configurable cross-origin access controls with defensive security headers
- **HTTPS Support**: Ollama backend HTTPS connectivity with secure deployment guidelines

### Changed
- **Error Handling**: Standardized error responses across all routes with proper HTTP status codes:
  - `504 Gateway Timeout` for upstream timeouts
  - `502 Bad Gateway` for connection refused errors
  - Custom error handling for malformed JSON and auth failures
- **Stream Control**: Flow control added to chat streaming to prevent memory exhaustion
- **Browser Compatibility**: Graceful fallback for UUID generation using `crypto.randomUUID()` with synchronous Math.random()

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- **File Uploads**: Path traversal prevention in filename sanitization
- **Chat Streaming**: Malformed chunk handling and stream reader cleanup to prevent memory leaks
- **Concurrent Requests**: Concurrency locking via `state.busy` to prevent duplicate chat requests
- **Configuration Validation**: Strict validation of port bounds, host format, URL scheme, and upload limits

### Security
- Bearer token authentication for API routes
- Filename sanitization to prevent directory traversal
- Rate limiting to prevent abuse (60 req/min with 15s retry-after window)
- Sensitive field redaction in logs
- CORS headers and security hardening headers (`X-Content-Type-Options`, `X-Frame-Options`)

### Performance
- In-memory caching for model tags and context recommendations (5-minute TTL)
- Visibility-based polling (slows when tab inactive, resumes on activation)
- Stream reader cleanup with try/finally pattern

### Testing
- Complete unit test suite with 79+ automated tests covering:
  - Configuration validation (`test_config.py`)
  - Context handling (`test_context.py`)
  - File extraction (`test_file_extract.py`)
  - Security controls (`test_security.py`)
  - Rate limiting (`test_rate_limiter.py`)
  - Ollama proxy errors (`test_ollama_proxy.py`)
  - System info parsing (`test_system_info.py`)
- Integration tests for all HTTP API routes (`test_handler_endpoints.py`)

### Documentation
- Comprehensive JSDoc comments across all JavaScript modules
- Configuration documentation with examples
- Security and TLS best practices (see README.md "Security" section)
- Systemd service configuration guide
- Upload format specifications
- Model runtime and context size explanations

### Features
- Export conversations to JSON with metadata preservation
- Import conversations with validation and deduplication
- Keyboard shortcuts: `Ctrl+N` (new conversation), `Ctrl+Esc` (close settings)
- Persistent settings (temperature, context size, system prompt) across reloads
- Online/offline status monitoring with automatic reconnect on upstream failures
- Hardware-based context size recommendations using 95% GPU memory heuristic

### Maintenance
- Parameterized constants for context window calculations
- Standardized error response shapes across all routes
- Separated route handlers with security decorators/helpers
- EditorConfig and .editorconfig added
- pytest and ruff linting configuration in pyproject.toml

---

## [0.9.0] - Previous Release

### Added
- Initial release of Ollama Console web interface
- Basic chat functionality with streaming support
- Model list display and switching
- File upload for prompt context attachment
- Machine statistics display

---

## Version History Summary

| Version | Date       | Highlights                                    |
|---------|------------|-----------------------------------------------|
| 1.0.0   | 2026-09-26 | Complete audit implementation, security hardening, full test coverage |
| 0.9.0   | -          | Initial release                              |

---

## Known Issues

- None at this time. All identified audit findings have been addressed.

## Support

For issues and contributions:
- Check the README.md for documentation
- Review configuration examples in `config.example.json`
- Run unit tests before deploying changes
