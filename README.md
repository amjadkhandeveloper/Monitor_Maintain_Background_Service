# Service Monitor - Multi-Platform Executable Monitor

A Python-based web application for monitoring and controlling services (JAR, EXE, BAT, SH files) running on Windows, macOS, and Linux. This tool helps you detect when services become unresponsive or stuck, monitor their resource utilization, and manage them through an intuitive web dashboard.

## Features

- 🔍 **Automatic Detection**: Automatically detects all running services (JAR, EXE, BAT, SH files)
- 📊 **Real-time Monitoring**: Monitor CPU and memory utilization in real-time
- 🎛️ **Service Control**: Start, stop, and restart services
- 🖥️ **Multi-Platform Support**: 
  - **Windows**: Supports `.jar`, `.exe`, `.bat` files
  - **macOS/Linux**: Supports `.jar`, `.sh` files
- 📈 **Detailed Information**: View comprehensive details about each service including:
  - Process ID (PID)
  - CPU and memory usage
  - Uptime and start time
  - Number of threads
  - Network connections
  - Command line arguments
- 🎨 **Modern Web Dashboard**: Beautiful, responsive web interface
- ⚡ **Smart Auto-Refresh**: Dashboard refreshes every 20 seconds (pauses when editing)
- 🔄 **Auto-Restart Feature**: Automatically restart services based on CPU, memory, or MSMQ queue thresholds
- 📁 **Subfolder Support**: Supports organized folder structure where each subfolder contains its matching executable
- 🔗 **MSMQ Queue Monitoring (Windows)**: Automatically matches MSMQ queue names to folder names and monitors message counts
- 💾 **Persistent Storage**: All configurations saved to `monitor_config.json` and persist across restarts

## Requirements

- Python 3.7 or higher
- Windows, macOS, or Linux operating system
- Java Runtime Environment (JRE) installed (for running JAR files)
- For `.sh` files on macOS/Linux: Ensure scripts have execute permissions

## Installation

1. **Clone or download this repository**

2. **Install Python dependencies**:
   
   **On Windows:**
   ```bash
   pip install -r requirements.txt
   ```
   
   **On macOS/Linux:**
   ```bash
   pip3 install -r requirements.txt
   ```

## Usage

1. **Start the monitoring server**:
   
   **On Windows:**
   ```bash
   python app.py
   ```
   Or double-click `start_monitor.bat`
   
   **On macOS/Linux:**
   ```bash
   python3 app.py
   ```
   Or run:
   ```bash
   ./start_monitor.sh
   ```

2. **Access the dashboard**:
   Open your web browser and navigate to:
   ```
   http://localhost:5001
   ```
   
   **Note**: The default port is 5001 (to avoid conflicts with macOS AirPlay Receiver on port 5000). 
   You can specify a different port when starting:
   ```bash
   python3 app.py 8080
   ```

3. **Monitor your services**:
   - Set the folder path where your executable files are located
   - **Folder Structure Support**: The application supports two folder structures:
     
     **Structure 1: Subfolders (Recommended)**
     ```
     Main Folder: C:\Program Files (x86)\Cellocator\Integration Package\
     ├── CorrelatorMax_ITLFMS_5000\
     │   └── CorrelatorMax_ITLFMS_5000.exe
     ├── CorrelatorMax_ITLFMS_6000\
     │   └── CorrelatorMax_ITLFMS_6000.exe
     └── CorrelatorMax_ITLFMS_6001\
         └── CorrelatorMax_ITLFMS_6001.jar
     ```
     - Each subfolder contains an executable file
     - **Folder name must match executable filename** (without extension, case-insensitive)
     - Example: Folder `CorrelatorMax_ITLFMS_5000` contains `CorrelatorMax_ITLFMS_5000.exe`
     - Services execute from within their subfolder (working directory set automatically)
     
     **Structure 2: Direct Files (Backward Compatible)**
     ```
     Main Folder: C:\MyServices\
     ├── Service1.jar
     ├── Service2.exe
     └── Service3.bat
     ```
     - Executable files directly in the main folder
     - Still supported for backward compatibility
   
   - View all available executable files/subfolders in the left sidebar (30% width):
     - **Windows**: `.jar`, `.exe`, `.bat` files
     - **macOS/Linux**: `.jar`, `.sh` files
     - Subfolders are displayed with their executables nested underneath
   - View running services in the right panel (70% width)
   - Click on any executable file in the sidebar to start it
   - File types are color-coded with badges (JAR, EXE, BAT, SH)
   - View CPU and memory utilization for each service
   - **MSMQ Queue Monitoring (Windows Only)**:
     - Queue names are automatically matched to folder names
     - Example: Queue `correlatormax_6000` matches folder `CorrelatorMax_ITLFMS_6000`
     - Queue message count is displayed for each running service
     - Queue-based auto-restart available (independent of CPU/Memory thresholds)
   - Click "Details" to see comprehensive information about a service
   - Use "Stop" to terminate a service
   - Use "Restart" to restart a service
   - **Enable Auto-Restart**: Toggle auto-restart for any service
   - **Set CPU Threshold**: Configure when auto-restart should trigger (default: 80%)
   - **Set Memory Threshold**: Configure memory limit for auto-restart (default: 1000 MB)
   - **Set Queue Threshold**: Configure MSMQ queue message limit for auto-restart (default: 10,000 messages, Windows only)
   - **Automatic Monitoring**: Services are checked every 30 seconds for high CPU, memory, or queue message count

## Important: Detached Process Execution

**Services started through this monitor run as detached processes** - they will continue running even if you stop the monitoring application. This means:

- ✅ Services survive Flask app shutdown
- ✅ Services run independently of the monitor
- ✅ You can safely restart the monitor without affecting running services
- ✅ Services can only be stopped through the dashboard or system process management

This is achieved by:
- **Windows**: Using `DETACHED_PROCESS` and `CREATE_NEW_PROCESS_GROUP` flags
- **macOS/Linux**: Using `start_new_session=True` to create detached processes

## Auto-Restart Feature

The monitor includes an **automatic restart feature** based on CPU and memory utilization:

- **Enable/Disable**: Toggle auto-restart for individual services via the dashboard
- **CPU Threshold**: Set custom CPU threshold (0-100%) - default is 80%
- **Memory Threshold**: Set custom memory threshold (100 MB - 10 GB) - default is 1000 MB (1 GB)
- **Dual Monitoring**: Auto-restart triggers when **either** CPU **OR** memory exceeds threshold
- **Automatic Monitoring**: Background thread checks CPU and memory usage every 30 seconds
- **Smart Restart**: When threshold is exceeded:
  - Service is stopped gracefully
  - **2-minute delay** (120 seconds) to allow memory cleanup and better performance
  - Service is automatically restarted
- **Status Indicators**: 
  - Green: Auto-restart enabled (shows both thresholds)
  - Yellow: Currently restarting (with 2-min delay)
  - Red: Auto-restart disabled

**Benefits:**
- Prevents services from getting stuck with high CPU usage
- Prevents memory leaks and excessive memory consumption
- Automatically frees memory by restarting services
- 2-minute delay ensures proper cleanup before restart
- Services remain available even during restart process
- Dual threshold monitoring catches both CPU spikes and memory leaks

## Configuration Storage

All settings are **persistently stored** in `monitor_config.json`:

- ✅ **Auto-restart configurations** (CPU and memory thresholds)
- ✅ **Folder path** for executable files
- ✅ **Survives Flask app restarts**
- ✅ **Stored by service name** (not PID) - survives service restarts

**Location**: `monitor_config.json` (in the same directory as `app.py`)

**Example configuration**:
```json
{
  "auto_restart": {
    "my-service.jar": {
      "enabled": true,
      "cpu_threshold": 85.0,
      "memory_threshold_mb": 1500.0,
      "jar_name": "my-service.jar"
    }
  },
  "folder_path": "/path/to/jar/folder"
}
```

See `STORAGE_INFO.md` for more details about configuration storage.

## Dashboard Features

### Smart Auto-Refresh
- Dashboard refreshes every **20 seconds** (configurable)
- **Automatically pauses** when you're editing input fields
- Resumes after you finish editing
- Prevents interruptions while configuring thresholds

### File Type Support
- **JAR files**: Java applications (all platforms)
- **EXE files**: Windows executables (Windows only)
- **BAT files**: Windows batch scripts (Windows only)
- **SH files**: Shell scripts (macOS/Linux only)

### Visual Indicators
- Color-coded file type badges
- CPU usage bars (red if > 80%)
- Memory usage bars (red if > 1GB)
- Auto-restart status indicators

## API Endpoints

The application provides REST API endpoints for programmatic access:

- `GET /api/services` - Get list of all services with status and utilization
- `GET /api/service/<pid>` - Get detailed information about a specific service
- `POST /api/service/<pid>/stop` - Stop a service
- `POST /api/service/<pid>/restart` - Restart a service (with 2-minute delay)
- `POST /api/service/<pid>/start` - Start a service (requires jar_path in request body)
- `POST /api/service/<pid>/auto-restart` - Configure auto-restart (enable/disable, set CPU and memory thresholds)
- `GET /api/service/<pid>/auto-restart` - Get auto-restart configuration for a service
- `POST /api/folder/set` - Set the folder path for executable files
- `GET /api/folder/jars` - List all executable files in the configured folder

## Troubleshooting

### Service not detected
- Ensure the service is running a supported file type (`.jar`, `.exe`, `.bat`, `.sh`)
- For JAR files: Check that the process has a `.jar` file in its command line arguments
- For `.sh` files: Ensure the script has execute permissions (`chmod +x script.sh`)

### Cannot stop/start services
- Ensure you have administrator privileges if required
- Check that the executable file path is accessible
- Verify that Java is in your system PATH (for JAR files)
- For `.sh` files: Ensure they have execute permissions

### Services continue running after stopping the monitor
- This is **expected behavior** - services are started as detached processes
- Services will continue running independently
- To stop services, use the dashboard "Stop" button or system process manager
- This ensures services remain available even if the monitor needs to be restarted

### High CPU/Memory Usage
- Services showing high utilization (CPU > 80% or Memory > 1GB) are highlighted in red
- Use the "Restart" button to restart stuck services
- Enable auto-restart to automatically handle high usage
- Check service details for more information about resource usage

### Auto-restart not working
- Ensure auto-restart is enabled for the service
- Check that thresholds are set correctly
- Verify the service is running (auto-restart only works for running services)
- Check Flask app logs for any errors

### Configuration not persisting
- Check that `monitor_config.json` file exists and is writable
- Verify file permissions in the application directory
- Check Flask app logs for configuration save errors

## Security Notes

- This application runs on `0.0.0.0:5001` by default (port 5001 to avoid macOS AirPlay Receiver conflict), making it accessible from other machines on your network
- **IMPORTANT**: Set the `FLASK_SECRET_KEY` environment variable for production use:
  ```bash
  export FLASK_SECRET_KEY='your-secret-key-here'
  ```
- Consider adding authentication for production deployments
- Be cautious when exposing this service on public networks
- Never commit sensitive information like API keys, tokens, or passwords to the repository
- The `monitor_config.json` file is excluded from Git (contains local settings)

## File Structure

```
ProcessProgram/
├── app.py                 # Main Flask application
├── service_monitor.py     # Service monitoring and control logic
├── config_storage.py      # Persistent configuration storage
├── constants.py           # ⚙️ DEFAULT VALUES - Change queue threshold here!
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── STORAGE_INFO.md       # Configuration storage documentation
├── monitor_config.json   # Persistent configuration (created automatically)
├── templates/
│   └── dashboard.html     # Web dashboard UI
├── start_monitor.sh      # macOS/Linux startup script
└── start_monitor.bat      # Windows startup script
```

## Changing Default Queue Threshold

**To change the default MSMQ queue threshold (the number that triggers auto-restart):**

1. **Open `constants.py` file**
2. **Find this line** (around line 13):
   ```python
   DEFAULT_QUEUE_THRESHOLD = 10000  # Default MSMQ queue message threshold
   ```
3. **Change the number** to your desired value, for example:
   ```python
   DEFAULT_QUEUE_THRESHOLD = 25000  # Auto-restart when queue has 25,000+ messages
   ```
4. **Save the file**
5. **Restart the application** - The new value will be used for all new services

**Note:** 
- This value is used as the default for new services
- Individual services can still override this through the dashboard UI
- Changes in `constants.py` only affect new services; existing services keep their configured values
- The threshold can be set between 1 and 1,000,000 messages

## License

This project is provided as-is for monitoring and managing services.

## Support

For issues, questions, or contributions, please refer to the repository's issue tracker.
