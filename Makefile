# Development and install tasks for terminal-velocity, driven by uv.
.PHONY: dev run test lint fmt install package clean

dev:
	uv sync

run:
	uv run terminal-velocity $(ARGS)

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

fmt:
	uv run ruff format src tests
	uv run ruff check --fix src tests

install:
	uv tool install --force .

package:
	rm -rf dist
	uv build

clean:
	rm -rf .venv dist build *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
