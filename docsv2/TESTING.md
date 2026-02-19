# eidosSpeech v2 - Testing Guide

This document explains how to run the automated test suite for eidosSpeech v2.

## 1. Prerequisites

Ensure you have the test dependencies installed:
```bash
pip install pytest pytest-asyncio httpx coverage
```

## 2. Directory Structure

```
tests/
├── conftest.py          # Global fixtures (DB, Client)
├── pytest.ini           # Configuration
├── unit/                # Unit tests (Models, Config)
├── integration/         # Integration tests (Auth, TTS, RateLimit)
├── security/            # Security tests (XSS, Injection)
└── stress/              # Performance tests (Concurrency)
```

## 3. Running Tests

### Run All Tests
To run the full suite:
```bash
# Windows
run_tests.bat

# Linux/Mac
pytest -v tests/
```

### Run Specific Category
```bash
pytest tests/unit -v
pytest tests/integration -v
pytest tests/security -v
```

### Run with Coverage Report
```bash
pytest --cov=app tests/
coverage html  # Generates htmlcov/index.html
```

## 4. Test Scenarios

### Unit Tests
- `test_config_models.py`: Verifies app configuration loading and DB model constraints.

### Integration Tests
- `test_auth_flow.py`: Full end-to-end registration -> verify -> login flow.
- `test_rate_limiter.py`: Verifies logic for Anonymous vs Registered limits.
- `test_tts_proxy.py`: Mocks TTS engine to test caching and proxy rotation logic.

### Security Tests
- `test_security.py`: Attempts authentication bypass and XSS injection.

### Stress Tests
- `test_performance.py`: Sends concurrent requests to verify thread-safety and semaphore.

## 5. Troubleshooting

**Common Issues:**
- `ModuleNotFoundError`: Run `pip install -r requirements.txt`.
- `IntegrityError`: Check DB constraints in expected test data.
- `AsyncSession` error: Ensure dependencies are injected correctly with `Depends()`.
