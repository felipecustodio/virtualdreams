# VirtualDreams — task runner
# Prerequisites: uv, cargo (rustup), yt-dlp, ffmpeg
# Install just: https://github.com/casey/just

set dotenv-load := true

# Show available recipes
default:
    @just --list

# ── Setup ────────────────────────────────────────────────────────────────────

# Install all dependencies and build the Rust binary
setup: _python-deps build
    @echo "✓ Setup complete. Copy .env.example to .env and edit as needed."

# Install Python dependencies (including dev extras)
_python-deps:
    uv sync --extra dev

# ── Rust binary ──────────────────────────────────────────────────────────────

# Build the chorus-detector release binary
build:
    cargo build --release --manifest-path chorus-detector/Cargo.toml
    @echo "✓ Binary: chorus-detector/target/release/chorus-detector"

# Build debug binary (faster compile, slower runtime)
build-debug:
    cargo build --manifest-path chorus-detector/Cargo.toml

# ── Run ──────────────────────────────────────────────────────────────────────

# Start the API server (reads HOST/PORT from .env)
run:
    uv run virtualdreams

# Start with auto-reload (useful during development)
dev:
    uv run uvicorn virtualdreams.main:app --reload --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"

# ── Test ─────────────────────────────────────────────────────────────────────

# Run all tests (Python + Rust)
test: test-python test-rust

# Run Python test suite
test-python:
    uv run pytest -v

# Run Rust unit tests
test-rust:
    cargo test --manifest-path chorus-detector/Cargo.toml

# Run a specific Python test file (e.g.: just test-file tests/test_routes.py)
test-file FILE:
    uv run pytest {{ FILE }} -v

# ── Lint & format ────────────────────────────────────────────────────────────

# Check linting and formatting
lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/

# Auto-fix lint issues and reformat
fmt:
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/

# Run type checker
typecheck:
    uv run ty check src/

# Run all checks (lint + typecheck)
check: lint typecheck

# ── Utilities ────────────────────────────────────────────────────────────────

# Smoke-test the chorus-detector binary on a generated WAV
smoke-test-binary:
    @echo "Generating 30s test WAV..."
    python3 -c "import wave,struct,math; sr=22050; dur=30; f=wave.open('/tmp/vd_test_input.wav','w'); f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr); [f.writeframes(struct.pack('<h',int(32767*math.sin(2*math.pi*440*i/sr)))) for i in range(sr*dur)]; f.close(); print('Input: /tmp/vd_test_input.wav')"
    ./chorus-detector/target/release/chorus-detector \
        /tmp/vd_test_input.wav /tmp/vd_test_output.wav --duration 15
    @echo "Output: /tmp/vd_test_output.wav"
    python3 -c "import os; size=os.path.getsize('/tmp/vd_test_output.wav'); expected=15*22050*4; print('File size: %d bytes (expected ~%d)' % (size,expected)); print('OK' if abs(size-expected)<500 else 'Unexpected size')"

# ── Docker ───────────────────────────────────────────────────────────────────

# Build the Docker image
docker-build:
    docker build -t virtualdreams .

# Run the container (PORT env var respected, default 8000)
docker-run:
    docker run --rm -p "${PORT:-8000}:8000" virtualdreams

# Start with docker compose (build if needed)
docker-up:
    docker compose up --build

# Stop docker compose
docker-down:
    docker compose down

# ── Utilities ─────────────────────────────────────────────────────────────────

# Remove compiled artifacts and caches
clean:
    cargo clean --manifest-path chorus-detector/Cargo.toml
    find . -type d -name __pycache__ -not -path './.venv/*' | xargs rm -rf
    rm -rf .pytest_cache .ruff_cache
