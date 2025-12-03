# Configuration Storage Information

## Where Auto-Restart Values Are Stored

### 1. **Persistent Storage (File)**
**Location**: `monitor_config.json` (in the same directory as `app.py`)

**Format**:
```json
{
  "auto_restart": {
    "service-name.jar": {
      "enabled": true,
      "cpu_threshold": 85.0,
      "memory_threshold_mb": 1500.0,
      "jar_name": "service-name.jar"
    }
  },
  "folder_path": "/path/to/jar/folder"
}
```

**Key Points**:
- ✅ **Persists across Flask app restarts**
- ✅ **Stored by service name** (not PID) - survives service restarts
- ✅ **Automatically loaded** when Flask app starts
- ✅ **File is created automatically** if it doesn't exist
- ✅ **Excluded from Git** (in `.gitignore`) - local settings only

### 2. **In-Memory Cache (Runtime)**
**Location**: `auto_restart_config` dictionary in `app.py`

**Format**:
```python
{
  pid: {
    'enabled': True,
    'cpu_threshold': 85.0,
    'memory_threshold_mb': 1500.0,
    'jar_name': 'service-name.jar',
    'restarting': False  # Runtime flag, not persisted
  }
}
```

**Key Points**:
- ⚡ **Fast access** during runtime
- 🔄 **Keyed by PID** for active processes
- ❌ **Lost when Flask app restarts**
- ✅ **Auto-populated** from persistent storage when services start

## How It Works

1. **When you set thresholds**:
   - Values are saved to `monitor_config.json` (by service name)
   - Values are also cached in memory (by PID)

2. **When Flask app starts**:
   - Loads all configs from `monitor_config.json`
   - When services are detected, matches them by name and loads configs into memory

3. **When service restarts**:
   - Old PID is removed from memory
   - New PID gets config from persistent storage (by service name)
   - Config persists because it's stored by name, not PID

4. **When Flask app restarts**:
   - All in-memory configs are lost
   - Configs are reloaded from `monitor_config.json` when services are detected

## File Location

The `monitor_config.json` file is stored in:
```
/Users/Amjad/Documents/ProcessProgram/monitor_config.json
```

## Backup Recommendation

Since the config file contains your custom thresholds, consider backing it up:
```bash
cp monitor_config.json monitor_config.json.backup
```

## Viewing Current Config

You can view the current configuration:
```bash
cat monitor_config.json
```

Or in Python:
```python
from config_storage import load_config
config = load_config()
print(config)
```

