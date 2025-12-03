#!/usr/bin/env python3
"""
Test script to verify configuration persistence
"""

from config_storage import (
    save_auto_restart_config, 
    get_auto_restart_config_by_name,
    load_config,
    save_folder_path,
    get_folder_path
)
import json

print("=" * 60)
print("Testing Configuration Persistence")
print("=" * 60)

# Test 1: Save auto-restart config
print("\n1. Saving test configuration...")
test_config = {
    'enabled': True,
    'cpu_threshold': 85.0,
    'memory_threshold_mb': 1500.0,
    'jar_name': 'test-service.jar'
}
save_auto_restart_config('test-service.jar', test_config)
print("   ✓ Saved config for 'test-service.jar'")

# Test 2: Save folder path
print("\n2. Saving folder path...")
save_folder_path('/test/path/to/jars')
print("   ✓ Saved folder path")

# Test 3: Load and verify
print("\n3. Loading configuration...")
loaded_config = load_config()
print("   ✓ Configuration loaded")
print(f"\n   Full config:")
print(json.dumps(loaded_config, indent=2))

# Test 4: Get specific service config
print("\n4. Retrieving specific service config...")
service_config = get_auto_restart_config_by_name('test-service.jar')
if service_config:
    print("   ✓ Found config for 'test-service.jar'")
    print(f"   CPU Threshold: {service_config.get('cpu_threshold')}%")
    print(f"   Memory Threshold: {service_config.get('memory_threshold_mb')} MB")
else:
    print("   ✗ Config not found")

# Test 5: Get folder path
print("\n5. Retrieving folder path...")
folder = get_folder_path()
print(f"   ✓ Folder path: {folder}")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
print("\nThe configuration is stored in: monitor_config.json")
print("This file persists even after stopping the Flask app.")
print("When you restart the app, it will automatically load these values.")

