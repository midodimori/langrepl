.PHONY: install lint-fix test pre-commit clean

install:
	uv sync --all-groups
	uv run pre-commit install

lint-fix:
	find src tests -name "*.py" -type f -exec uv run pyupgrade --py313-plus {} + || true
	uv run autoflake --recursive --remove-all-unused-imports --remove-unused-variables --in-place src tests
	uv run isort src tests --profile black
	uv run black src tests
	uv run mypy src tests --check-untyped-defs

test:
	uv run pytest tests

pre-commit:
	uv run pre-commit run --all-files

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
