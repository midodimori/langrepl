# Format code
lint-fix:
	find src tests -name "*.py" -type f -exec uv run pyupgrade --py313-plus {} +
	uv run autoflake --recursive --remove-all-unused-imports --remove-unused-variables --in-place src tests
	uv run isort src tests --profile black
	uv run black src tests
	uv run mypy src tests --check-untyped-defs
	@echo "✨ Code formatted!"

test:
	uv run pytest tests
	@echo "✨ Tests completed!"