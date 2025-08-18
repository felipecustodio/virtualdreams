#!/usr/bin/env python3
"""
Simple test script to verify Docker setup and dependencies.
This test can run without a bot token.
"""

import sys
import os

def test_imports():
    """Test that all required packages can be imported"""
    try:
        # Core dependencies
        import youtube_dl
        import redis
        import pydub
        import pysndfx
        import pychorus
        import logzero
        from telegram.ext import Updater
        print("✅ All Python packages imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_system_commands():
    """Test that system audio tools are available"""
    import subprocess
    
    tools = [
        ('sox', '--version'),
        ('ffmpeg', '-version')
    ]
    all_good = True
    
    for tool, version_arg in tools:
        try:
            result = subprocess.run([tool, version_arg], capture_output=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ {tool} is available")
            else:
                print(f"❌ {tool} returned error code {result.returncode}")
                all_good = False
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"❌ {tool} is not available: {e}")
            all_good = False
    
    return all_good

def test_redis_connection():
    """Test Redis connection (optional)"""
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        client = redis.from_url(redis_url)
        client.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"⚠️  Redis connection failed (this is OK if running without Redis): {e}")
        return False

def test_file_operations():
    """Test file operations in cache directory"""
    try:
        cache_dir = '/app/cache' if os.path.exists('/app/cache') else './cache'
        test_file = os.path.join(cache_dir, 'test.txt')
        
        # Ensure directory exists
        os.makedirs(cache_dir, exist_ok=True)
        
        # Write test file
        with open(test_file, 'w') as f:
            f.write('test')
        
        # Read test file
        with open(test_file, 'r') as f:
            content = f.read()
        
        # Clean up
        os.remove(test_file)
        
        if content == 'test':
            print("✅ File operations working")
            return True
        else:
            print("❌ File operations failed")
            return False
            
    except Exception as e:
        print(f"❌ File operations failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Virtual Dreams Docker setup...\n")
    
    tests = [
        ("Python imports", test_imports),
        ("System tools", test_system_commands),
        ("File operations", test_file_operations),
        ("Redis connection", test_redis_connection),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n📋 Testing {name}...")
        results.append(test_func())
    
    print(f"\n🎯 Test Results:")
    success_count = sum(results[:-1])  # Don't count Redis as required
    total_required = len(results) - 1
    
    print(f"   Required tests passed: {success_count}/{total_required}")
    if results[-1]:  # Redis test
        print("   Optional Redis test: ✅ PASSED")
    else:
        print("   Optional Redis test: ⚠️  SKIPPED/FAILED")
    
    if success_count == total_required:
        print("\n🎉 All required tests passed! Docker setup is working correctly.")
        return 0
    else:
        print("\n❌ Some required tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())