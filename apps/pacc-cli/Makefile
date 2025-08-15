# PACC Development Makefile

.PHONY: help install install-dev test test-unit test-integration test-e2e test-security test-performance lint format type-check security-check coverage clean docs build build-sdist build-wheel build-check install-build-deps test-build publish-test publish-prod publish-check publish-prepare verify-release

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
	@echo "Build & Distribution:"
	@echo "  build            Build source and wheel distributions"
	@echo "  build-sdist      Build source distribution only"
	@echo "  build-wheel      Build wheel distribution only"
	@echo "  build-check      Validate distributions with twine"
	@echo "  install-build-deps Install build dependencies"
	@echo "  test-build       Test wheel installation"
	@echo ""
	@echo "Publishing:"
	@echo "  publish-prepare  Prepare for publishing (validate, build, test)"
	@echo "  publish-test     Publish to Test PyPI"
	@echo "  publish-prod     Publish to production PyPI"
	@echo "  publish-check    Validate distributions before publishing"
	@echo "  verify-release   Verify published release"
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

# Build & Distribution targets
build:
	python scripts/build.py build

build-sdist:
	python scripts/build.py build --dist-type sdist

build-wheel:
	python scripts/build.py build --dist-type wheel

build-check:
	python scripts/build.py check

install-build-deps:
	python scripts/build.py install-deps

test-build:
	python scripts/build.py test

# Complete build workflow
build-all: clean install-build-deps build build-check
	@echo "Complete build workflow finished"

# Build and test locally
build-local: build
	pip install --force-reinstall dist/*.whl
	@echo "PACC installed from local wheel"
	@echo "Test with: pacc --version"

# Publishing targets
publish-prepare:
	@echo "📋 Preparing for publication..."
	python scripts/publish.py validate
	python scripts/publish.py build
	python scripts/publish.py test-install
	@echo "✅ Ready for publishing"

publish-test:
	@echo "📤 Publishing to Test PyPI..."
	python scripts/publish.py publish --test
	@echo "✅ Published to Test PyPI"
	@echo "Install with: pip install --index-url https://test.pypi.org/simple/ pacc"

publish-prod:
	@echo "📤 Publishing to PyPI..."
	@echo "⚠️  This will publish to production PyPI!"
	python scripts/publish.py publish --prod
	@echo "✅ Published to PyPI"
	@echo "Install with: pip install pacc"

publish-check:
	@echo "🔍 Checking distributions..."
	python scripts/publish.py validate
	python scripts/build.py check
	@echo "✅ Distributions are valid"

verify-release:
	@echo "🔍 Verifying release..."
	@if [ -z "$(VERSION)" ]; then \
		echo "❌ Error: VERSION not specified"; \
		echo "Usage: make verify-release VERSION=x.y.z"; \
		exit 1; \
	fi
	python scripts/publish.py verify --version $(VERSION)
	@echo "✅ Release $(VERSION) verified"

# Complete release workflow
release: pre-release publish-prepare
	@echo "🚀 Starting release workflow..."
	python scripts/publish.py release --test-first
	@echo "✅ Release complete!"

# Quick release (skip test PyPI)
release-quick: pre-release publish-prepare
	@echo "🚀 Starting quick release..."
	python scripts/publish.py release
	@echo "✅ Release complete!"