# ── Stage 1: build the Rust chorus-detector binary ───────────────────────────
FROM rust:1-slim-bookworm AS rust-builder

WORKDIR /build
COPY chorus-detector/ ./
RUN cargo build --release

# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.14-slim-bookworm

# System deps: ffmpeg + curl (for yt-dlp bootstrap)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp standalone binary (always the latest stable release)
RUN curl -fsSL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
        -o /usr/local/bin/yt-dlp \
    && chmod +x /usr/local/bin/yt-dlp

# uv (Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# chorus-detector binary from the Rust build stage
COPY --from=rust-builder /build/target/release/chorus-detector /usr/local/bin/chorus-detector

WORKDIR /app

# Install Python deps (production only, no dev extras)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application source
COPY src/ ./src/

ENV PATH="/app/.venv/bin:$PATH"
ENV CHORUS_DETECTOR_BIN=/usr/local/bin/chorus-detector
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["virtualdreams"]
