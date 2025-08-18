# Modern Caching System

The Virtual Dreams bot now features a modern, multi-layered caching system that significantly improves performance and efficiency.

## Architecture

### Three-Layer Cache System
1. **Memory Cache** (L1): Ultra-fast in-memory LRU cache for frequently accessed metadata
2. **Redis Cache** (L2): Distributed caching for scalability and session persistence  
3. **File Cache** (L3): Organized file system storage for processed audio files

### Key Improvements
- **Smart Cache Keys**: Uses video IDs/hashes instead of titles to prevent collisions
- **TTL Support**: Configurable expiration (default: 7 days)
- **Size Management**: LRU eviction when cache exceeds size limit (default: 500MB)
- **Cache Statistics**: Monitor hit rates, miss rates, and performance via `/stats` command
- **Graceful Degradation**: Works without Redis, falls back to file-based caching

## Configuration

Set these environment variables in your `.env` file:

```bash
# Required
TOKEN=your_telegram_bot_token

# Optional Redis (recommended for production)
REDIS_URL=redis://localhost:6379/0

# Optional Cache Settings
CACHE_DIR=cache           # Cache directory (default: cache)
CACHE_SIZE_MB=500        # Max cache size in MB (default: 500)
CACHE_TTL_DAYS=7         # Cache expiration in days (default: 7)
```

## New Bot Commands

- `/vapor "song name"` - Create vaporwave music (cached automatically)
- `/vapor YouTube_URL` - Process YouTube URL (cached automatically) 
- `/stats` - View cache performance statistics

## Cache Statistics

The `/stats` command shows:
- Total cached files and size
- Cache hit rate percentage  
- Number of hits, misses, and evictions
- Memory cache usage
- Redis availability status

## Performance Benefits

- **Faster Response**: Cached audio delivered instantly
- **Reduced Processing**: No re-processing of previously requested songs
- **Better Resource Usage**: Intelligent eviction prevents disk space issues
- **Scalability**: Redis support enables multi-instance deployments
- **Monitoring**: Built-in metrics for performance optimization

## Backward Compatibility

The new caching system is fully backward compatible. Existing deployments will automatically benefit from improved caching without any configuration changes.