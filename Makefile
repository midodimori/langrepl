.PHONY: install lint-fix test pre-commit bump-patch bump-minor bump-major clean

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

bump-patch:
	uv run bump-my-version bump patch

bump-minor:
	uv run bump-my-version bump minor

bump-major:
	uv run bump-my-version bump major

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
