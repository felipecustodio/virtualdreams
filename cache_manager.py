# -*- coding: utf-8 -*-

"""cache_manager.py: Modern caching system for Virtual Dreams Bot."""

__author__ = "Felipe S. Custódio"
__license__ = "GPL"

import os
import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from collections import OrderedDict
import threading

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from logzero import logger


class CacheManager:
    """Modern multi-layered cache manager with TTL, LRU eviction, and Redis support."""
    
    def __init__(self, 
                 cache_dir: str = "cache",
                 redis_url: Optional[str] = None,
                 max_cache_size_mb: int = 500,
                 default_ttl: int = 7 * 24 * 3600,  # 7 days
                 memory_cache_size: int = 100):
        """
        Initialize the cache manager.
        
        Args:
            cache_dir: Directory for file-based cache storage
            redis_url: Redis connection URL (optional)
            max_cache_size_mb: Maximum cache size in MB
            default_ttl: Default time-to-live in seconds
            memory_cache_size: Maximum number of items in memory cache
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self.default_ttl = default_ttl
        self.memory_cache_size = memory_cache_size
        
        # In-memory cache for quick access (LRU)
        self._memory_cache: OrderedDict = OrderedDict()
        self._cache_lock = threading.RLock()
        
        # Redis client for distributed caching
        self.redis_client = None
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("Redis cache backend initialized")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using fallback caching.")
                self.redis_client = None
        elif redis_url and not REDIS_AVAILABLE:
            logger.warning("Redis URL provided but redis package not available")
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'size_bytes': 0
        }
        
        # Metadata file for tracking cache entries
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self._load_metadata()
        
        # Cleanup old entries on startup
        self._cleanup_expired()
    
    def _load_metadata(self):
        """Load cache metadata from disk."""
        self.metadata = {}
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    self.metadata = json.load(f)
                logger.info(f"Loaded {len(self.metadata)} cache metadata entries")
        except Exception as e:
            logger.warning(f"Failed to load cache metadata: {e}")
            self.metadata = {}
    
    def _save_metadata(self):
        """Save cache metadata to disk."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache metadata: {e}")
    
    def _generate_cache_key(self, video_id: str, operation: str = "vapor") -> str:
        """
        Generate a unique cache key for a video.
        
        Args:
            video_id: YouTube video ID or URL
            operation: Type of operation (e.g., 'vapor', 'chorus')
            
        Returns:
            Hashed cache key
        """
        # Extract video ID from URL if needed
        if 'watch?v=' in video_id:
            video_id = video_id.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in video_id:
            video_id = video_id.split('youtu.be/')[1].split('?')[0]
        
        # Create hash from video ID and operation
        key_data = f"{video_id}:{operation}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _get_file_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{cache_key}.wav"
    
    def _update_memory_cache(self, key: str, data: Any):
        """Update the in-memory LRU cache."""
        with self._cache_lock:
            if key in self._memory_cache:
                # Move to end (most recently used)
                self._memory_cache.move_to_end(key)
            else:
                self._memory_cache[key] = data
                # Evict oldest if over limit
                while len(self._memory_cache) > self.memory_cache_size:
                    oldest_key = next(iter(self._memory_cache))
                    del self._memory_cache[oldest_key]
                    self.stats['evictions'] += 1
    
    def _cleanup_expired(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = []
        
        for key, meta in self.metadata.items():
            if current_time > meta.get('expires_at', float('inf')):
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_cache_entry(key)
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _enforce_size_limit(self):
        """Enforce cache size limits using LRU eviction."""
        current_size = sum(meta.get('size', 0) for meta in self.metadata.values())
        
        if current_size <= self.max_cache_size_bytes:
            return
        
        # Sort by last access time (LRU)
        sorted_entries = sorted(
            self.metadata.items(),
            key=lambda x: x[1].get('last_accessed', 0)
        )
        
        bytes_to_remove = current_size - self.max_cache_size_bytes
        bytes_removed = 0
        
        for key, meta in sorted_entries:
            if bytes_removed >= bytes_to_remove:
                break
            
            file_size = meta.get('size', 0)
            self._remove_cache_entry(key)
            bytes_removed += file_size
            self.stats['evictions'] += 1
        
        logger.info(f"Evicted cache entries to free {bytes_removed} bytes")
    
    def _remove_cache_entry(self, key: str):
        """Remove a cache entry from all storage layers."""
        # Remove from file system
        file_path = self._get_file_path(key)
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Failed to remove cache file {file_path}: {e}")
        
        # Remove from metadata
        if key in self.metadata:
            del self.metadata[key]
        
        # Remove from memory cache
        with self._cache_lock:
            if key in self._memory_cache:
                del self._memory_cache[key]
        
        # Remove from Redis
        if self.redis_client:
            try:
                self.redis_client.delete(f"cache_meta:{key}")
            except Exception as e:
                logger.error(f"Failed to remove from Redis: {e}")
    
    def get_cached_audio(self, video_id: str, video_title: str = "") -> Optional[Path]:
        """
        Get cached audio file if it exists and is valid.
        
        Args:
            video_id: YouTube video ID or URL
            video_title: Video title for logging
            
        Returns:
            Path to cached audio file or None if not found/expired
        """
        cache_key = self._generate_cache_key(video_id)
        current_time = time.time()
        
        # Check memory cache first
        with self._cache_lock:
            if cache_key in self._memory_cache:
                meta = self._memory_cache[cache_key]
                if current_time <= meta.get('expires_at', float('inf')):
                    # Update access time and move to end
                    meta['last_accessed'] = current_time
                    self._memory_cache.move_to_end(cache_key)
                    self.stats['hits'] += 1
                    logger.info(f"Cache HIT (memory) for {video_title} [{cache_key}]")
                    return self._get_file_path(cache_key)
        
        # Check Redis cache
        if self.redis_client:
            try:
                redis_meta = self.redis_client.get(f"cache_meta:{cache_key}")
                if redis_meta:
                    meta = json.loads(redis_meta)
                    if current_time <= meta.get('expires_at', float('inf')):
                        # Update access time
                        meta['last_accessed'] = current_time
                        self.redis_client.setex(
                            f"cache_meta:{cache_key}",
                            int(meta.get('expires_at', current_time + self.default_ttl) - current_time),
                            json.dumps(meta)
                        )
                        self._update_memory_cache(cache_key, meta)
                        self.stats['hits'] += 1
                        logger.info(f"Cache HIT (redis) for {video_title} [{cache_key}]")
                        return self._get_file_path(cache_key)
            except Exception as e:
                logger.error(f"Redis cache check failed: {e}")
        
        # Check file system cache
        if cache_key in self.metadata:
            meta = self.metadata[cache_key]
            if current_time <= meta.get('expires_at', float('inf')):
                file_path = self._get_file_path(cache_key)
                if file_path.exists():
                    # Update access time
                    meta['last_accessed'] = current_time
                    self._update_memory_cache(cache_key, meta)
                    
                    # Update Redis if available
                    if self.redis_client:
                        try:
                            ttl = int(meta.get('expires_at', current_time + self.default_ttl) - current_time)
                            self.redis_client.setex(
                                f"cache_meta:{cache_key}",
                                ttl,
                                json.dumps(meta)
                            )
                        except Exception as e:
                            logger.error(f"Failed to update Redis: {e}")
                    
                    self.stats['hits'] += 1
                    logger.info(f"Cache HIT (disk) for {video_title} [{cache_key}]")
                    return file_path
        
        # Cache miss
        self.stats['misses'] += 1
        logger.info(f"Cache MISS for {video_title} [{cache_key}]")
        return None
    
    def store_audio(self, video_id: str, audio_file_path: str, video_title: str = "", ttl: Optional[int] = None) -> str:
        """
        Store audio file in cache.
        
        Args:
            video_id: YouTube video ID or URL
            audio_file_path: Path to audio file to cache
            video_title: Video title for logging
            ttl: Time-to-live in seconds (optional)
            
        Returns:
            Cache key for the stored audio
        """
        cache_key = self._generate_cache_key(video_id)
        current_time = time.time()
        expires_at = current_time + (ttl or self.default_ttl)
        
        # Copy file to cache directory
        cache_file_path = self._get_file_path(cache_key)
        try:
            import shutil
            shutil.copy2(audio_file_path, cache_file_path)
            file_size = cache_file_path.stat().st_size
        except Exception as e:
            logger.error(f"Failed to copy file to cache: {e}")
            raise
        
        # Create metadata
        meta = {
            'video_id': video_id,
            'video_title': video_title,
            'created_at': current_time,
            'last_accessed': current_time,
            'expires_at': expires_at,
            'size': file_size,
            'cache_key': cache_key
        }
        
        # Store in all cache layers
        self.metadata[cache_key] = meta
        self._update_memory_cache(cache_key, meta)
        
        # Store in Redis
        if self.redis_client:
            try:
                ttl_seconds = int(expires_at - current_time)
                self.redis_client.setex(
                    f"cache_meta:{cache_key}",
                    ttl_seconds,
                    json.dumps(meta)
                )
            except Exception as e:
                logger.error(f"Failed to store in Redis: {e}")
        
        # Save metadata to disk
        self._save_metadata()
        
        # Enforce size limits
        self._enforce_size_limit()
        
        logger.info(f"Cached audio for {video_title} [{cache_key}] (size: {file_size} bytes)")
        return cache_key
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_files = len(self.metadata)
        total_size = sum(meta.get('size', 0) for meta in self.metadata.values())
        hit_rate = self.stats['hits'] / max(self.stats['hits'] + self.stats['misses'], 1) * 100
        
        return {
            'total_files': total_files,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'max_size_mb': self.max_cache_size_bytes // (1024 * 1024),
            'hit_rate_percent': round(hit_rate, 2),
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'evictions': self.stats['evictions'],
            'redis_available': self.redis_client is not None,
            'memory_cache_size': len(self._memory_cache)
        }
    
    def clear_cache(self):
        """Clear all cache entries."""
        # Remove all files
        for cache_file in self.cache_dir.glob("*.wav"):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.error(f"Failed to remove {cache_file}: {e}")
        
        # Clear metadata
        self.metadata.clear()
        self._save_metadata()
        
        # Clear memory cache
        with self._cache_lock:
            self._memory_cache.clear()
        
        # Clear Redis
        if self.redis_client:
            try:
                for key in self.redis_client.scan_iter(match="cache_meta:*"):
                    self.redis_client.delete(key)
            except Exception as e:
                logger.error(f"Failed to clear Redis cache: {e}")
        
        logger.info("Cache cleared")