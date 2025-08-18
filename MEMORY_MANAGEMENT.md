# Memory Management for Pychorus

This document describes the memory management improvements implemented to address pychorus memory consumption issues in the Virtual Dreams bot.

## Problem Statement

The original issue was that pychorus (chorus detection library) was consuming too much memory, causing the bot to crash. The library performs complex audio analysis that can require significant memory for longer audio files.

## Solution Overview

We implemented a comprehensive memory management system that includes:

1. **Real-time memory monitoring** - Track memory usage during chorus detection
2. **Memory limits** - Enforce maximum memory usage to prevent crashes  
3. **Timeout protection** - Prevent hanging on problematic files
4. **Progressive fallback** - Try smaller durations if memory limits are exceeded
5. **Aggressive cleanup** - Force garbage collection and cleanup between attempts

## Key Components

### Memory Monitor (`memory_utils.py`)

The `MemoryMonitor` class provides:
- Real-time memory usage tracking
- Configurable memory limits (default: 256MB for chorus detection)
- Timeout protection (default: 20 seconds)
- Automatic cleanup and garbage collection

### Safe Chorus Detection (`safe_find_chorus`)

A wrapper around the original `find_and_output_chorus` function that:
- Runs pychorus with memory and timeout limits
- Provides detailed logging of memory usage
- Handles failures gracefully
- Performs cleanup after each attempt

### Progressive Duration Reduction

The system now tries multiple approaches:
1. Start with 15-second chorus detection
2. If memory/timeout limits exceeded, try 10 seconds
3. If still failing, try 5 seconds
4. If all chorus detection fails, fall back to using first segment

## Configuration

### Memory Limits
- **Chorus detection**: 256MB (conservative limit to prevent crashes)
- **Stress testing**: 32MB (for testing memory enforcement)

### Timeouts
- **Chorus detection**: 20 seconds (prevents hanging on problematic files)
- **Testing**: 2-10 seconds (for validation)

### Retry Logic
- **Maximum attempts**: 3 (prevents excessive resource usage)
- **Duration reduction**: 5 seconds per attempt (15s → 10s → 5s)

## Memory Usage Patterns

Based on testing, typical memory usage:
- **Baseline**: ~16MB (empty bot)
- **Audio loading**: +80-100MB (AudioSegment operations)
- **Chorus detection**: +150-200MB (pychorus processing)
- **Peak usage**: Can exceed 400MB for large files without limits

With the new system:
- **Memory growth** is monitored in real-time
- **Limits are enforced** at 256MB for production use
- **Cleanup occurs** between attempts and after completion
- **Graceful degradation** when limits are exceeded

## Testing

The implementation includes comprehensive tests:

### `test_memory.py`
- Basic memory monitoring functionality
- Memory limit enforcement
- Timeout protection
- Memory stress testing

### `test_chorus_isolated.py`
- Memory-safe chorus detection with realistic audio
- Large file handling with strict memory limits
- Progressive fallback mechanism validation

### Test Results
- ✅ Memory limits successfully prevent excessive usage
- ✅ Timeout mechanism prevents hanging
- ✅ Graceful degradation when chorus detection fails
- ✅ Memory cleanup working as expected

## Usage

The memory management is automatically applied when using the `vapor()` function. No changes to the bot interface are required.

### Example Log Output
```
[123] Starting chorus detection with 15s duration
[123] Memory usage at before_chorus_detection: 98.48 MB
[123] Memory limit exceeded: 256.52 MB > 256 MB
[123] Chorus detection failed due to memory limit
[123] Chorus detection attempt 2/3 with duration 10s
[123] Memory usage at after_chorus_search: 145.23 MB
```

## Benefits

1. **Prevents crashes** - Memory limits prevent the bot from consuming excessive memory
2. **Maintains functionality** - Progressive fallback ensures users still get results
3. **Better resource management** - Aggressive cleanup reduces memory footprint
4. **Improved reliability** - Timeout protection prevents hanging
5. **Enhanced monitoring** - Detailed logging helps with troubleshooting

## Future Improvements

The current implementation addresses the immediate memory issues. Future enhancements could include:

1. **Dynamic memory limits** based on available system memory
2. **Worker process isolation** for heavy audio processing
3. **Alternative chorus detection algorithms** with lower memory requirements
4. **Caching improvements** to reduce repeated processing
5. **Audio preprocessing** to reduce file sizes before chorus detection

## Migration Notes

The changes are backward compatible. Existing functionality is preserved, but with added memory safety. No changes to bot commands or user interface are required.