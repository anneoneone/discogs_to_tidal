# Tests Directory

This directory contains all test files organized by type:

## Structure

- `unit/` - Unit tests for individual functions and classes
- `integration/` - Integration tests for module interactions
- `conftest.py` - Pytest configuration and shared fixtures

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run only unit tests
python -m pytest tests/unit/

# Run only integration tests
python -m pytest tests/integration/

# Run with coverage
python -m pytest tests/ --cov=src/discogs_to_tidal
```

## Test Organization

- Each module should have corresponding test files
- Use descriptive test names that explain what is being tested
- Group related tests in classes when appropriate
- Use fixtures for common test data and setup
