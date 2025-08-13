# PACC Development Makefile

.PHONY: help install install-dev test test-unit test-integration test-e2e test-security test-performance lint format type-check security-check coverage clean docs

# Default target
help:
	@echo "PACC Development Commands"
	@echo "========================"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-e2e         Run end-to-end tests only"
	@echo "  test-security    Run security tests only"
	@echo "  test-performance Run performance benchmarks"
	@echo "  coverage         Generate test coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint             Run code linting"
	@echo "  format           Format code with black and isort"
	@echo "  type-check       Run type checking with mypy"
	@echo "  security-check   Run security analysis"
	@echo ""
	@echo "Documentation:"
	@echo "  docs             Generate documentation"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean            Clean build artifacts and cache"

# Installation
install:
	uv pip install -e .

install-dev:
	uv pip install -e .
	uv pip install -r requirements-test.txt

# Testing
test:
	pytest -v --cov=pacc --cov-report=term-missing --cov-report=html

test-unit:
	pytest tests/unit/ -v -m "unit"

test-integration:
	pytest tests/integration/ -v -m "integration"

test-e2e:
	pytest tests/e2e/ -v -m "e2e"

test-security:
	pytest tests/ -v -m "security"

test-performance:
	pytest tests/performance/ -v -m "performance" --benchmark-only

test-cross-platform:
	pytest tests/ -v -m "cross_platform"

# Coverage
coverage:
	pytest --cov=pacc --cov-report=html --cov-report=term-missing --cov-fail-under=80
	@echo "Coverage report generated in htmlcov/"

coverage-xml:
	pytest --cov=pacc --cov-report=xml

# Code Quality
lint:
	flake8 pacc tests
	pylint pacc
	bandit -r pacc -f json -o security-report.json || true

format:
	black pacc tests
	isort pacc tests

format-check:
	black --check pacc tests
	isort --check-only pacc tests

type-check:
	mypy pacc

# Security
security-check:
	bandit -r pacc
	safety check
	
security-report:
	bandit -r pacc -f json -o security-report.json
	safety check --json --output safety-report.json || true

# Quality checks (run all)
quality: format-check lint type-check security-check

# Performance benchmarks
benchmark:
	pytest tests/performance/ --benchmark-only --benchmark-sort=mean

benchmark-compare:
	pytest tests/performance/ --benchmark-only --benchmark-compare

# Test with specific markers
test-fast:
	pytest -v -m "not slow and not performance"

test-slow:
	pytest -v -m "slow"

# Parallel testing
test-parallel:
	pytest -n auto

# Documentation
docs:
	@echo "API documentation available in docs/api_reference.md"
	@echo "Security guide available in docs/security_guide.md"
	@echo "Run 'python -m http.server 8000' in docs/ to serve documentation"

# Maintenance
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf __pycache__/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	rm -f security-report.json
	rm -f safety-report.json

# Development workflow
dev-setup: install-dev
	@echo "Development environment ready!"
	@echo "Run 'make test' to verify installation"

# CI/CD targets
ci-test: quality test coverage-xml

# Pre-commit checks
pre-commit: format quality test-fast

# Release preparation
pre-release: clean quality test coverage
	@echo "Release checks completed successfully"

# Debugging helpers
debug-env:
	@echo "Python version: $(shell python --version)"
	@echo "Pytest version: $(shell pytest --version)"
	@echo "Current directory: $(shell pwd)"
	@echo "PYTHONPATH: $$PYTHONPATH"

# Performance profiling
profile:
	python -m cProfile -o profile.stats -m pytest tests/performance/
	@echo "Profile saved to profile.stats"
	@echo "View with: python -m pstats profile.stats"

# Test with different Python versions (requires pyenv or similar)
test-versions:
	@echo "Testing with Python 3.8..."
	python3.8 -m pytest tests/unit/ || true
	@echo "Testing with Python 3.9..."
	python3.9 -m pytest tests/unit/ || true
	@echo "Testing with Python 3.10..."
	python3.10 -m pytest tests/unit/ || true
	@echo "Testing with Python 3.11..."
	python3.11 -m pytest tests/unit/ || true

# Generate test report
test-report:
	pytest --html=test-report.html --self-contained-html --cov=pacc --cov-report=html
	@echo "Test report generated: test-report.html"
	@echo "Coverage report in: htmlcov/index.html"