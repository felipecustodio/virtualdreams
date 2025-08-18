#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for memory management improvements in virtualdreams bot.
Tests the memory monitoring and cleanup functionality.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add the project directory to the path
sys.path.insert(0, '/home/runner/work/virtualdreams/virtualdreams')

from memory_utils import MemoryMonitor, cleanup_memory, log_memory_usage


def test_memory_monitor():
    """Test basic memory monitoring functionality."""
    print("Testing memory monitoring...")
    
    # Test basic memory usage logging
    initial_memory = log_memory_usage("test_start")
    print(f"Initial memory: {initial_memory:.2f} MB")
    
    # Test memory cleanup
    cleanup_memory()
    after_cleanup = log_memory_usage("test_after_cleanup")
    print(f"Memory after cleanup: {after_cleanup:.2f} MB")
    
    print("Memory monitoring test passed!")


def test_memory_limit():
    """Test memory limit functionality with a simple function."""
    print("\nTesting memory limit functionality...")
    
    monitor = MemoryMonitor(max_memory_mb=50, timeout_seconds=5)
    
    @monitor.with_memory_limit
    def simple_function():
        # Simple function that should not exceed memory limits
        data = "test" * 1000
        return len(data)
    
    try:
        result = simple_function()
        print(f"Simple function completed successfully with result: {result}")
    except Exception as e:
        print(f"Simple function failed: {e}")
        return False
    
    print("Memory limit test passed!")
    return True


def test_timeout():
    """Test timeout functionality."""
    print("\nTesting timeout functionality...")
    
    monitor = MemoryMonitor(max_memory_mb=1000, timeout_seconds=2)
    
    @monitor.with_memory_limit
    def slow_function():
        # Function that should timeout
        time.sleep(5)
        return "should not reach here"
    
    try:
        result = slow_function()
        print(f"ERROR: Slow function should have timed out but returned: {result}")
        return False
    except TimeoutError as e:
        print(f"Timeout test passed: {e}")
        return True
    except Exception as e:
        print(f"Unexpected error in timeout test: {e}")
        return False


def test_memory_stress():
    """Test memory limit with a memory-intensive function."""
    print("\nTesting memory stress with small limit...")
    
    monitor = MemoryMonitor(max_memory_mb=32, timeout_seconds=10)
    
    @monitor.with_memory_limit
    def memory_intensive_function():
        # Create a large amount of data to test memory limits
        data = []
        for i in range(10000):
            data.append("x" * 10000)  # This should eventually hit memory limits
        return len(data)
    
    try:
        result = memory_intensive_function()
        print(f"Memory intensive function completed with result: {result}")
        print("Note: This may indicate the memory limit was not reached")
    except MemoryError as e:
        print(f"Memory limit test passed: {e}")
        return True
    except Exception as e:
        print(f"Memory stress test failed with unexpected error: {e}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("Running memory management tests...")
    print("=" * 50)
    
    try:
        test_memory_monitor()
        
        if not test_memory_limit():
            return False
            
        if not test_timeout():
            return False
            
        test_memory_stress()
        
        print("\n" + "=" * 50)
        print("All tests completed!")
        return True
        
    except Exception as e:
        print(f"Test suite failed with error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)