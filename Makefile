.PHONY: help venv install install-dev test test-cov lint format clean docs build
.DEFAULT_GOAL := help

PYTHON := .venv/bin/python
PIP := .venv/bin/pip
BLACK := .venv/bin/black
ISORT := .venv/bin/isort
FLAKE8 := .venv/bin/flake8
MYPY := .venv/bin/mypy
SRC_DIR := src
TEST_DIR := tests

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

#> === Setup commands ===

venv: ## Create virtual environment
	python -m venv .venv
	@echo "Virtual environment created. Activate with: source .venv/bin/activate"

install: ## Install the package and runtime dependencies
	$(PIP) install -e .

install-dev: ## Install the package with development dependencies
	$(PIP) install -e ".[dev,test]"

dev-setup: ## Set up development environment
	$(MAKE) venv
	source .venv/bin/activate
	$(MAKE) install-dev
	@echo "Development environment ready!"

#> === Test commands ===

test: ## Run all tests
	$(PYTHON) -m pytest $(TEST_DIR)/ -v

test-unit: ## Run unit tests only
	$(PYTHON) -m pytest $(TEST_DIR)/unit/ -v

test-integration: ## Run integration tests only
	$(PYTHON) -m pytest $(TEST_DIR)/integration/ -v

test-cov: ## Run tests with coverage
	$(PYTHON) -m pytest $(TEST_DIR)/ --cov=$(SRC_DIR) --cov-report=html --cov-report=term

test-coverage: ## Run tests with coverage and XML output for CI
	$(PYTHON) -m pytest $(TEST_DIR)/ --cov=$(SRC_DIR) --cov-report=html --cov-report=term --cov-report=xml

#> === Quality commands ===

pre-commit: ## Run pre-commit hooks on all files
	.venv/bin/pre-commit run --all-files

pre-commit-install: ## Install pre-commit hooks
	.venv/bin/pre-commit install

lint: ## Run linting checks
	$(BLACK) --check $(SRC_DIR) $(TEST_DIR)
	$(ISORT) --check-only $(SRC_DIR) $(TEST_DIR)
	$(FLAKE8) $(SRC_DIR) $(TEST_DIR)
	$(MYPY) $(SRC_DIR)

format: ## Format code
	$(BLACK) $(SRC_DIR) $(TEST_DIR)
	$(ISORT) $(SRC_DIR) $(TEST_DIR)

check: ## Run all checks (lint + test)
	$(MAKE) lint
	$(MAKE) test

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +

docs: ## Generate documentation
	@echo "Documentation generation - to be implemented"

#> Not implemented yet
# build: ## Build the package
# 	$(PYTHON) -m build

release-check: ## Check if ready for release
	$(MAKE) clean
	$(MAKE) lint
	$(MAKE) test-cov
	$(MAKE) build
	@echo "Release checks passed!"

# Development commands
run: ## Run the CLI help
	.venv/bin/discogs-to-tidal --help

sync: ## Sync Discogs collection to Tidal
	.venv/bin/discogs-to-tidal sync

style-sync: ## Create Tidal playlists organized by styles/subgenres
	.venv/bin/discogs-to-tidal style-sync

test-auth: ## Test authentication with services
	.venv/bin/discogs-to-tidal test-auth

tidal-auth: ## Check and setup Tidal authorization (authenticate if needed)
	.venv/bin/discogs-to-tidal tidal-auth

discogs-auth: ## Check and setup Discogs authorization (prompt for token if needed)
	.venv/bin/discogs-to-tidal discogs-auth

config: ## Show configuration information
	.venv/bin/discogs-to-tidal config-info

folders: ## List available Discogs collection folders
	.venv/bin/discogs-to-tidal list-folders

run-old: ## Run the old main.py (legacy)
	$(PYTHON) main.py

run-tests-watch: ## Run tests in watch mode (requires pytest-watch)
	ptw $(TEST_DIR)/
