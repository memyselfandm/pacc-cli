# Contributing to PACC

## Development Setup

1. Install development dependencies:
```bash
uv pip install -e ".[dev]"
```

2. Install pre-commit hooks:
```bash
pre-commit install
```

## Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality:

- **Ruff**: Fast Python linter and formatter
- **MyPy**: Type checking
- **Bandit**: Security vulnerability scanning
- **Standard hooks**: YAML/JSON validation, trailing whitespace, etc.

## Running Linters Manually

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run specific tools
uv run ruff check .
uv run ruff format .
uv run mypy pacc
uv run bandit -c pyproject.toml -r pacc
```

## Testing

```bash
# Run tests
make test
# or: uv run pytest

# Run with coverage
uv run pytest --cov=pacc
```
