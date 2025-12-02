# Java JAR Service Monitor

A Python-based web application for monitoring and controlling Java JAR services running on Windows. This tool helps you detect when Java services become unresponsive or stuck, monitor their resource utilization, and manage them through an intuitive web dashboard.

## Features

- 🔍 **Automatic Detection**: Automatically detects all running Java JAR services
- 📊 **Real-time Monitoring**: Monitor CPU and memory utilization in real-time
- 🎛️ **Service Control**: Start, stop, and restart Java services
- 📈 **Detailed Information**: View comprehensive details about each service including:
  - Process ID (PID)
  - CPU and memory usage
  - Uptime and start time
  - Number of threads
  - Network connections
  - Command line arguments
- 🎨 **Modern Web Dashboard**: Beautiful, responsive web interface
- ⚡ **Auto-refresh**: Dashboard automatically refreshes every 5 seconds

## Requirements

- Python 3.7 or higher
- Windows or macOS operating system
- Java Runtime Environment (JRE) installed (for running JAR files)

## Design after running

<img width="1606" height="871" alt="Screenshot 2025-12-02 at 5 34 55 PM" src="https://github.com/user-attachments/assets/2ee9103e-ee0e-4e03-86a2-0a975123c747" />

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
   - Set the folder path where your JAR files are located
   - View all available JAR files in the left sidebar (30% width)
   - View running services in the right panel (70% width)
   - Click on a JAR file in the sidebar to start it
   - View CPU and memory utilization for each service
   - Click "Details" to see comprehensive information about a service
   - Use "Stop" to terminate a service
   - Use "Restart" to restart a service
   - **Enable Auto-Restart**: Toggle auto-restart for any service
   - **Set CPU Threshold**: Configure when auto-restart should trigger (default: 80%)
   - **Automatic Monitoring**: Services are checked every 30 seconds for high CPU usage

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

The monitor includes an **automatic restart feature** based on CPU utilization:

- **Enable/Disable**: Toggle auto-restart for individual services via the dashboard
- **CPU Threshold**: Set custom CPU threshold (0-100%) - default is 80%
- **Automatic Monitoring**: Background thread checks CPU usage every 30 seconds
- **Smart Restart**: When CPU exceeds threshold:
  - Service is stopped gracefully
  - **2-minute delay** (120 seconds) to allow memory cleanup and better performance
  - Service is automatically restarted
- **Status Indicators**: 
  - Green: Auto-restart enabled
  - Yellow: Currently restarting (with 2-min delay)
  - Red: Auto-restart disabled

**Benefits:**
- Prevents services from getting stuck with high CPU usage
- Automatically frees memory by restarting services
- 2-minute delay ensures proper cleanup before restart
- Services remain available even during restart process

## API Endpoints

The application provides REST API endpoints for programmatic access:

- `GET /api/services` - Get list of all Java JAR services
- `GET /api/service/<pid>` - Get detailed information about a specific service
- `POST /api/service/<pid>/stop` - Stop a service
- `POST /api/service/<pid>/restart` - Restart a service (with 2-minute delay)
- `POST /api/service/<pid>/start` - Start a service (requires jar_path in request body)
- `POST /api/service/<pid>/auto-restart` - Configure auto-restart (enable/disable, set CPU threshold)
- `GET /api/service/<pid>/auto-restart` - Get auto-restart configuration for a service
- `POST /api/folder/set` - Set the folder path for JAR files
- `GET /api/folder/jars` - List all JAR files in the configured folder

## Troubleshooting

### Service not detected
- Ensure the Java process is actually running a JAR file (not just a Java application)
- Check that the process has a `.jar` file in its command line arguments

### Cannot stop/start services
- Ensure you have administrator privileges if required
- Check that the JAR file path is accessible
- Verify that Java is in your system PATH

### Services continue running after stopping the monitor
- This is **expected behavior** - services are started as detached processes
- Services will continue running independently
- To stop services, use the dashboard "Stop" button or system process manager
- This ensures services remain available even if the monitor needs to be restarted

### High CPU/Memory Usage
- Services showing high utilization (CPU > 80% or Memory > 1GB) are highlighted in red
- Use the "Restart" button to restart stuck services
- Check service details for more information about resource usage

## Security Notes

- This application runs on `0.0.0.0:5001` by default (port 5001 to avoid macOS AirPlay Receiver conflict), making it accessible from other machines on your network
- **IMPORTANT**: Set the `FLASK_SECRET_KEY` environment variable for production use:
  ```bash
  export FLASK_SECRET_KEY='your-secret-key-here'
  ```
- Consider adding authentication for production deployments
- Be cautious when exposing this service on public networks
- Never commit sensitive information like API keys, tokens, or passwords to the repository

## License

This project is provided as-is for monitoring and managing Java services.

