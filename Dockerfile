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

# Bun for yt-dlp YouTube JS challenge solving
COPY --from=oven/bun:1 /usr/local/bin/bun /usr/local/bin/bun

# uv (Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# chorus-detector binary from the Rust build stage
COPY --from=rust-builder /build/target/release/chorus-detector /usr/local/bin/chorus-detector

WORKDIR /app

# Install Python dependencies first (layer cache: only re-runs when lock file changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project itself
COPY src/ ./src/
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV CHORUS_DETECTOR_BIN=/usr/local/bin/chorus-detector
ENV YTDLP_JS_RUNTIME=bun
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["virtualdreams"]
