#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script specifically for the safe_find_chorus function.
Creates a simple test audio file and tests the memory-safe chorus detection.
"""

import os
import sys
import tempfile
import wave
import numpy as np
from pathlib import Path

# Add the project directory to the path
sys.path.insert(0, '/home/runner/work/virtualdreams/virtualdreams')

from memory_utils import log_memory_usage


def create_test_audio(filename, duration_seconds=5, sample_rate=44100):
    """Create a simple test audio file."""
    print(f"Creating test audio file: {filename}")
    
    # Generate a simple sine wave
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), False)
    frequency = 440  # A4 note
    audio_data = np.sin(2 * np.pi * frequency * t)
    
    # Convert to 16-bit PCM
    audio_data = (audio_data * 32767).astype(np.int16)
    
    # Write to WAV file
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())
    
    print(f"Created test audio: {filename} ({duration_seconds}s)")
    return filename


def test_safe_find_chorus():
    """Test the safe_find_chorus function."""
    print("Testing safe_find_chorus function...")
    
    # Import here to avoid issues if dependencies aren't available
    try:
        from vapor import safe_find_chorus
    except ImportError as e:
        print(f"Cannot import safe_find_chorus: {e}")
        return False
    
    # Create temporary files
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, "test_input.wav")
        output_path = os.path.join(temp_dir, "test_chorus.wav")
        
        # Create test audio file
        create_test_audio(input_path, duration_seconds=10)
        
        log_memory_usage("before_safe_find_chorus_test")
        
        # Test the safe chorus detection
        try:
            result = safe_find_chorus(input_path, output_path, 5, "test_request_123")
            
            log_memory_usage("after_safe_find_chorus_test")
            
            print(f"safe_find_chorus result: {result}")
            
            # Check if output file exists (if chorus was found)
            if result and Path(output_path).exists():
                print(f"Output file created: {output_path}")
                file_size = Path(output_path).stat().st_size
                print(f"Output file size: {file_size} bytes")
            elif not result:
                print("No chorus found (this is normal for a simple sine wave)")
            else:
                print(f"Chorus detection returned {result} but no output file found")
            
            return True
            
        except Exception as e:
            print(f"safe_find_chorus test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Run the test."""
    print("Testing safe_find_chorus implementation...")
    print("=" * 50)
    
    try:
        if test_safe_find_chorus():
            print("\nTest completed successfully!")
            return True
        else:
            print("\nTest failed!")
            return False
    except Exception as e:
        print(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)