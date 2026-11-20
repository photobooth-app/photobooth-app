# Agent instructions

## Project overview

This repository contains the Python backend for photobooth-app, a FastAPI application with camera acquisition, media processing, persistence, and plugins. The Vue frontend is maintained in the separate `photobooth-frontend` repository; `src/web/frontend` contains the bundled frontend assets served by this app.

## Repository layout

- `src/photobooth/`: application code
  - `routers/`: HTTP and admin endpoints
  - `services/`: application services, camera backends, configuration, and media processing
  - `plugins/`: built-in plugins
  - `database/`: SQLAlchemy models, schemas, and Alembic migrations
- `src/tests/tests/`: pytest tests, organized around the application areas
- `src/tests/benchmarks/`: performance benchmarks
- `src/web/`: web assets served by the backend

Follow the nearest existing implementation and test when extending a feature. Keep API, service, and persistence responsibilities in their existing layers.

## Development and validation

- Python support starts at 3.11; use `uv` for environment and dependency management.
- Install development dependencies with `uv sync`.
- Run the app locally with `uv run photobooth`.
- Run the full configured lint, type-check, and formatting checks with `uv run poe lint`.
- Run the test suite with `uv run poe test`.
- For a focused test, use `uv run pytest -q path/to/test_file.py`.
- Format Python files with `uv run ruff format path/to/file.py`; use `uv run ruff check --fix path/to/file.py` only for applicable lint fixes.

Run the narrowest relevant tests and checks for a change. If a check cannot run in the current environment (for example, because a hardware-specific dependency is unavailable), report that explicitly rather than implying it passed.

The shared pytest fixtures configure GPIO with a mock pin factory. Prefer tests with mocks or fixtures over requiring physical cameras, GPIO devices, or other hardware.

## Change guidance

- Keep changes focused and preserve existing behavior unless the task calls for a behavior change.
- Add or update focused tests for behavior changes and bug fixes.
- When changing persisted models or schema behavior, inspect the existing Alembic migrations and add a migration when required; do not rewrite migrations that may already have been applied.
- Do not hand-edit hashed or minified files under `src/web/frontend`. Frontend source changes belong in the separate `photobooth-frontend` repository; update this repository's bundled assets only through its established frontend build workflow when that is part of the task.
- Do not hand-edit hashed or minified files under `src/web/sharepage`. Sharepage source changes belong in the separate `photobooth-sharepage` repository; update this repository's bundled assets only through its established sharepage build workflow when that is part of the task.
- Runtime and user data directories such as `config/`, `database/`, `media/`, `cache/`, `plugins/`, and `log/` are ignored by Git. Treat their contents as user data; do not delete, reset, or modify them unless explicitly requested.
- Do not commit credentials, local configuration, generated test output, or unrelated formatting changes.
