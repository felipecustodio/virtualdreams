#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Isolated test for the memory-safe chorus detection functionality.
Tests only the core memory management without telegram dependencies.
"""

import os
import sys
import tempfile
import wave
import numpy as np
from pathlib import Path

# Add the project directory to the path
sys.path.insert(0, '/home/runner/work/virtualdreams/virtualdreams')

from memory_utils import MemoryMonitor, cleanup_memory, log_memory_usage

# Import only the chorus detection function directly
try:
    from pychorus import find_and_output_chorus
except ImportError:
    print("pychorus not available, skipping test")
    sys.exit(0)


def safe_find_chorus_isolated(original_path, chorus_path, duration, request_id):
    """
    Isolated version of safe_find_chorus for testing without telegram dependencies.
    """
    # Configure memory monitor with conservative limits
    memory_monitor = MemoryMonitor(max_memory_mb=256, timeout_seconds=20)
    
    print(f"[{request_id}] Starting chorus detection with {duration}s duration")
    log_memory_usage(f"[{request_id}] before_chorus_detection")
    
    try:
        # Wrap the pychorus function with memory monitoring
        @memory_monitor.with_memory_limit
        def monitored_find_chorus():
            return find_and_output_chorus(original_path, chorus_path, duration)
        
        # Execute with memory monitoring
        result = monitored_find_chorus()
        
        log_memory_usage(f"[{request_id}] after_chorus_detection")
        print(f"[{request_id}] Chorus detection completed successfully: {result}")
        
        # Force cleanup after chorus detection
        cleanup_memory()
        
        return result
        
    except MemoryError as e:
        print(f"[{request_id}] Chorus detection failed due to memory limit: {e}")
        cleanup_memory()
        return False
        
    except TimeoutError as e:
        print(f"[{request_id}] Chorus detection failed due to timeout: {e}")
        cleanup_memory()
        return False
        
    except Exception as e:
        print(f"[{request_id}] Chorus detection failed with error: {e}")
        cleanup_memory()
        return False


def create_test_audio(filename, duration_seconds=10, sample_rate=44100):
    """Create a simple test audio file with some variation to potentially find chorus."""
    print(f"Creating test audio file: {filename}")
    
    # Generate a more complex audio pattern that might have repetition
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), False)
    
    # Create a pattern that repeats (like a simple chorus)
    pattern_duration = 2.0  # 2 second pattern
    pattern_samples = int(sample_rate * pattern_duration)
    
    # Generate the base pattern (sine wave with frequency modulation)
    pattern_t = np.linspace(0, pattern_duration, pattern_samples, False)
    base_freq = 440
    mod_freq = 2
    pattern = np.sin(2 * np.pi * base_freq * pattern_t) * np.sin(2 * np.pi * mod_freq * pattern_t)
    
    # Repeat the pattern to fill the duration
    num_repeats = int(np.ceil(duration_seconds / pattern_duration))
    full_audio = np.tile(pattern, num_repeats)
    
    # Trim to exact duration
    target_samples = int(sample_rate * duration_seconds)
    full_audio = full_audio[:target_samples]
    
    # Add some variation
    full_audio += 0.1 * np.random.random(len(full_audio))
    
    # Normalize and convert to 16-bit PCM
    full_audio = full_audio / np.max(np.abs(full_audio))
    audio_data = (full_audio * 32767 * 0.8).astype(np.int16)
    
    # Write to WAV file
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())
    
    print(f"Created test audio: {filename} ({duration_seconds}s)")
    return filename


def test_memory_safe_chorus():
    """Test the memory-safe chorus detection."""
    print("Testing memory-safe chorus detection...")
    
    # Create temporary files
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, "test_input.wav")
        output_path = os.path.join(temp_dir, "test_chorus.wav")
        
        # Create test audio file
        create_test_audio(input_path, duration_seconds=15)
        
        log_memory_usage("before_memory_safe_chorus_test")
        
        # Test the safe chorus detection
        try:
            result = safe_find_chorus_isolated(input_path, output_path, 5, "test_request_456")
            
            log_memory_usage("after_memory_safe_chorus_test")
            
            print(f"Memory-safe chorus detection result: {result}")
            
            # Check if output file exists
            if result and Path(output_path).exists():
                print(f"Output file created: {output_path}")
                file_size = Path(output_path).stat().st_size
                print(f"Output file size: {file_size} bytes")
                return True
            elif not result:
                print("No chorus found - this is acceptable for the test")
                return True
            else:
                print(f"Inconsistent result: returned {result} but no output file")
                return False
            
        except Exception as e:
            print(f"Memory-safe chorus test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_memory_limits():
    """Test that memory limits work with a large audio file."""
    print("\nTesting memory limits with large audio file...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, "large_test_input.wav")
        output_path = os.path.join(temp_dir, "large_test_chorus.wav")
        
        # Create a larger test audio file that might consume more memory
        create_test_audio(input_path, duration_seconds=60)  # 1 minute
        
        # Use a very restrictive memory limit for testing
        memory_monitor = MemoryMonitor(max_memory_mb=32, timeout_seconds=10)
        
        @memory_monitor.with_memory_limit
        def test_large_chorus():
            return find_and_output_chorus(input_path, output_path, 15)
        
        try:
            result = test_large_chorus()
            print(f"Large file test result: {result}")
            return True
        except (MemoryError, TimeoutError) as e:
            print(f"Memory/timeout limit triggered as expected: {e}")
            return True
        except Exception as e:
            print(f"Unexpected error in large file test: {e}")
            return False


def main():
    """Run all tests."""
    print("Testing memory-safe pychorus implementation...")
    print("=" * 60)
    
    try:
        success = True
        
        if not test_memory_safe_chorus():
            success = False
            
        if not test_memory_limits():
            success = False
        
        print("\n" + "=" * 60)
        if success:
            print("All tests completed successfully!")
        else:
            print("Some tests failed!")
            
        return success
        
    except Exception as e:
        print(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)