# VirtualDreams — task runner
# Prerequisites: Docker, uv (for local test/lint)
# Install just: https://github.com/casey/just

set dotenv-load := true

default:
    @just --list

# Start the server (Docker, rebuilds on change)
dev:
    docker compose up --build

# Stop the server
down:
    docker compose down

# Run the test suite locally
test:
    uv run pytest -v

# Auto-fix lint and formatting
fmt:
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/

# Check lint, formatting, and types
check:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/
    uv run ty check src/

# Remove build artifacts and caches
clean:
    find . -type d -name __pycache__ -not -path './.venv/*' | xargs rm -rf
    rm -rf .pytest_cache .ruff_cache
