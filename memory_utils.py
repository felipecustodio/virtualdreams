# -*- coding: utf-8 -*-
"""
Memory utilities for monitoring and managing memory usage during audio processing.
Specifically designed to handle pychorus memory consumption issues.
"""

import gc
import os
import signal
import psutil
import threading
import time
from functools import wraps
import logging

# Get logger for memory management
logger = logging.getLogger('virtualdreams.memory')


class MemoryMonitor:
    """Monitor and limit memory usage for functions."""
    
    def __init__(self, max_memory_mb=512, timeout_seconds=30):
        self.max_memory_mb = max_memory_mb
        self.timeout_seconds = timeout_seconds
        self.process = psutil.Process()
        
    def get_memory_usage_mb(self):
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024
    
    def monitor_memory_usage(self, func, args, kwargs, result_container):
        """Monitor memory usage of a function call."""
        try:
            initial_memory = self.get_memory_usage_mb()
            logger.debug("Initial memory usage: %.2f MB", initial_memory)
            
            result = func(*args, **kwargs)
            result_container['result'] = result
            result_container['success'] = True
            
            final_memory = self.get_memory_usage_mb()
            logger.debug("Final memory usage: %.2f MB", final_memory)
            logger.debug("Memory delta: %.2f MB", final_memory - initial_memory)
            
        except Exception as e:
            result_container['error'] = str(e)
            result_container['success'] = False
            logger.error("Function execution failed: %s", str(e))
        finally:
            # Force garbage collection
            gc.collect()
    
    def with_memory_limit(self, func):
        """Decorator to run function with memory and timeout limits."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            result_container = {'success': False, 'result': None, 'error': None}
            
            # Create thread for the actual function execution
            thread = threading.Thread(
                target=self.monitor_memory_usage,
                args=(func, args, kwargs, result_container)
            )
            
            # Start monitoring
            thread.start()
            start_time = time.time()
            
            # Monitor memory and timeout
            while thread.is_alive():
                current_memory = self.get_memory_usage_mb()
                elapsed_time = time.time() - start_time
                
                # Check memory limit
                if current_memory > self.max_memory_mb:
                    logger.warning("Memory limit exceeded: %.2f MB > %d MB", current_memory, self.max_memory_mb)
                    # Force garbage collection
                    gc.collect()
                    # Give one more chance
                    time.sleep(1)
                    current_memory = self.get_memory_usage_mb()
                    if current_memory > self.max_memory_mb:
                        logger.error("Memory limit still exceeded after GC: %.2f MB", current_memory)
                        raise MemoryError(f"Memory usage exceeded limit: {current_memory:.2f} MB > {self.max_memory_mb} MB")
                
                # Check timeout
                if elapsed_time > self.timeout_seconds:
                    logger.error("Timeout exceeded: %.2f s > %d s", elapsed_time, self.timeout_seconds)
                    raise TimeoutError(f"Function execution timeout after {elapsed_time:.2f} seconds")
                
                time.sleep(0.1)  # Check every 100ms
            
            thread.join()
            
            if not result_container['success']:
                if result_container['error']:
                    raise RuntimeError(result_container['error'])
                else:
                    raise RuntimeError("Function execution failed")
            
            return result_container['result']
        
        return wrapper


def cleanup_memory():
    """Force cleanup of memory and garbage collection."""
    gc.collect()
    
    
def log_memory_usage(stage_name):
    """Log current memory usage for debugging."""
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    logger.info("Memory usage at %s: %.2f MB", stage_name, memory_mb)
    return memory_mb