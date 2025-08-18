# Virtual Dreams Bot - Docker Setup

This document explains how to run the Virtual Dreams Telegram bot using Docker.

## Prerequisites

- Docker and Docker Compose installed
- A Telegram Bot Token (get one from [@BotFather](https://t.me/botfather))

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/felipecustodio/virtualdreams.git
   cd virtualdreams
   ```

2. Copy the environment template and configure your bot token:
   ```bash
   cp .env.example .env
   # Edit .env and add your Telegram bot token
   ```

3. Build and start the services:
   ```bash
   docker-compose up --build
   ```

## Services

The Docker setup includes:

- **virtualdreams**: The main Telegram bot application
- **redis**: Redis cache for improved performance

## Configuration

Environment variables can be set in the `.env` file:

- `TOKEN`: Your Telegram bot token (required)
- `REDIS_URL`: Redis connection URL (defaults to `redis://redis:6379`)
- `PORT`: Application port (defaults to 8443)

## Volumes

The setup creates the following volumes:

- `./cache`: Bot's working directory for temporary audio files
- `./logs`: Application logs
- `redis_data`: Redis persistent data

## Development

To run in development mode with live code changes:

```bash
# Build the image
docker-compose build

# Run with file watching (you'll need to rebuild on code changes)
docker-compose up
```

## Production

For production deployment:

1. Ensure your `.env` file has the correct production values
2. Run with detached mode:
   ```bash
   docker-compose up -d
   ```

## Troubleshooting

- Check logs: `docker-compose logs virtualdreams`
- Check Redis: `docker-compose logs redis`
- Restart services: `docker-compose restart`
- Clean rebuild: `docker-compose down && docker-compose up --build`