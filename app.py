"""
Java JAR Service Monitor - Main Flask Application
Monitors and controls Java JAR services running on Windows, macOS, and Linux
"""

from flask import Flask, render_template, jsonify, request
import json
import os
import threading
import time
from service_monitor import ServiceMonitor
from config_storage import (
    load_config, save_config, get_auto_restart_config_by_name,
    save_auto_restart_config, delete_auto_restart_config,
    get_folder_path, save_folder_path
)
import logging

app = Flask(__name__)
# SECRET_KEY should be set via environment variable for security
# Example: export FLASK_SECRET_KEY='your-secret-key-here'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'change-this-in-production-use-env-variable')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize service monitor
monitor = ServiceMonitor()

# In-memory cache for auto-restart config (keyed by PID for active processes)
# Persistent storage is in monitor_config.json (keyed by service_name)
auto_restart_config = {}  # {pid: config} - for active processes
auto_restart_lock = threading.Lock()

# Load persistent config on startup
persistent_config = load_config()
jar_folder_path = persistent_config.get('folder_path')

# Load auto-restart configs from persistent storage
logger.info(f"Loaded persistent config: {len(persistent_config.get('auto_restart', {}))} service configurations")


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/services', methods=['GET'])
def get_services():
    """Get list of all Java JAR services with their status and utilization"""
    global auto_restart_config
    try:
        services = monitor.get_all_services()
        
        # Add auto-restart configuration to each service
        # First check in-memory (by PID), then check persistent storage (by service name)
        with auto_restart_lock:
            for service in services:
                pid = service['pid']
                service_name = service.get('service_name') or service.get('jar_name', 'Unknown')
                
                # Check in-memory config first (for active processes)
                if pid in auto_restart_config:
                    service['auto_restart'] = auto_restart_config[pid]
                else:
                    # Check persistent storage by service name
                    persistent_config_data = get_auto_restart_config_by_name(service_name)
                    if persistent_config_data:
                        # Load into memory cache and remove restarting flag
                        config_copy = persistent_config_data.copy()
                        config_copy['restarting'] = False
                        auto_restart_config[pid] = config_copy
                        service['auto_restart'] = config_copy
                    else:
                        # Default config
                        service['auto_restart'] = {
                            'enabled': False,
                            'cpu_threshold': 80.0,
                            'memory_threshold_mb': 1000.0,  # Default 1GB
                            'restarting': False
                        }
        
        return jsonify({
            'success': True,
            'services': services
        })
    except Exception as e:
        logger.error(f"Error getting services: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/service/<int:pid>', methods=['GET'])
def get_service_details(pid):
    """Get detailed information about a specific service"""
    try:
        details = monitor.get_service_details(pid)
        if details:
            return jsonify({
                'success': True,
                'service': details
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Service not found'
            }), 404
    except Exception as e:
        logger.error(f"Error getting service details: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/service/<int:pid>/stop', methods=['POST'])
def stop_service(pid):
    """Stop a Java JAR service"""
    try:
        result = monitor.stop_service(pid)
        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Service {pid} stopped successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to stop service')
            }), 400
    except Exception as e:
        logger.error(f"Error stopping service: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/service/<int:pid>/start', methods=['POST'])
def start_service(pid):
    """Start a Java JAR service (requires jar_path in request body)"""
    try:
        data = request.get_json()
        jar_path = data.get('jar_path') if data else None
        
        if not jar_path:
            return jsonify({
                'success': False,
                'error': 'jar_path is required'
            }), 400
        
        result = monitor.start_service(jar_path)
        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Service started successfully',
                'pid': result.get('pid')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to start service')
            }), 400
    except Exception as e:
        logger.error(f"Error starting service: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/service/start', methods=['POST'])
def start_service_direct():
    """Start a Java JAR service directly (no PID required)"""
    try:
        data = request.get_json()
        jar_path = data.get('jar_path') if data else None
        
        if not jar_path:
            return jsonify({
                'success': False,
                'error': 'jar_path is required'
            }), 400
        
        result = monitor.start_service(jar_path)
        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Service started successfully',
                'pid': result.get('pid')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to start service')
            }), 400
    except Exception as e:
        logger.error(f"Error starting service: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/folder/set', methods=['POST'])
def set_folder_path():
    """Set the folder path where JAR files are located"""
    global jar_folder_path
    try:
        data = request.get_json()
        folder_path = data.get('folder_path') if data else None
        
        if not folder_path:
            return jsonify({
                'success': False,
                'error': 'folder_path is required'
            }), 400
        
        # Validate folder exists
        if not os.path.isdir(folder_path):
            return jsonify({
                'success': False,
                'error': f'Folder does not exist: {folder_path}'
            }), 400
        
        jar_folder_path = folder_path
        # Save to persistent storage
        save_folder_path(folder_path)
        return jsonify({
            'success': True,
            'message': 'Folder path set successfully',
            'folder_path': jar_folder_path
        })
    except Exception as e:
        logger.error(f"Error setting folder path: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/folder/jars', methods=['GET'])
def list_jar_files():
    """List all executable files (JAR, EXE, BAT, SH) in the configured folder"""
    global jar_folder_path
    import platform
    
    try:
        folder = request.args.get('folder_path', jar_folder_path)
        
        if not folder:
            return jsonify({
                'success': False,
                'error': 'No folder path configured. Please set folder path first.'
            }), 400
        
        if not os.path.isdir(folder):
            return jsonify({
                'success': False,
                'error': f'Folder does not exist: {folder}'
            }), 400
        
        # Get supported extensions for current OS
        system = platform.system()
        supported_exts = {
            'Windows': ['.jar', '.exe', '.bat'],
            'Darwin': ['.jar', '.sh'],  # macOS
            'Linux': ['.jar', '.sh']
        }
        extensions = supported_exts.get(system, ['.jar', '.exe', '.bat', '.sh'])
        
        executable_files = []
        try:
            for filename in os.listdir(folder):
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in extensions:
                    file_path = os.path.join(folder, filename)
                    if os.path.isfile(file_path):  # Only include files, not directories
                        file_size = os.path.getsize(file_path)
                        file_type = file_ext.upper().replace('.', '')
                        executable_files.append({
                            'name': filename,
                            'path': file_path,
                            'size_mb': round(file_size / (1024 * 1024), 2),
                            'type': file_type,
                            'extension': file_ext
                        })
            executable_files.sort(key=lambda x: (x['type'], x['name']))
        except PermissionError:
            return jsonify({
                'success': False,
                'error': f'Permission denied accessing folder: {folder}'
            }), 403
        
        return jsonify({
            'success': True,
            'jar_files': executable_files,  # Keep 'jar_files' key for backward compatibility
            'executable_files': executable_files,  # New key name
            'folder_path': folder,
            'supported_types': extensions
        })
    except Exception as e:
        logger.error(f"Error listing JAR files: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def restart_service_internal(pid, jar_name=None, delay_seconds=120):
    """Internal function to restart a service with configurable delay"""
    global jar_folder_path
    
    # Determine jar_path: use jar_name + folder_path if provided, otherwise use existing jar_path
    jar_path = None
    
    if jar_name and jar_folder_path:
        # Use folder path + jar name
        jar_path = os.path.join(jar_folder_path, jar_name)
        # Normalize path separators
        jar_path = os.path.normpath(jar_path)
        if not os.path.exists(jar_path):
            return {
                'success': False,
                'error': f'JAR file not found: {jar_path}'
            }
    else:
        # Fallback to getting jar_path from running service
        details = monitor.get_service_details(pid)
        if not details:
            return {
                'success': False,
                'error': 'Service not found'
            }
        
        jar_path = details.get('jar_path')
        if not jar_path:
            return {
                'success': False,
                'error': 'Could not determine JAR path for service. Please set folder path and provide jar_name.'
            }
    
    # Stop the service
    stop_result = monitor.stop_service(pid)
    if not stop_result['success']:
        return {
            'success': False,
            'error': f"Failed to stop service: {stop_result.get('error')}"
        }
    
    # Wait for the specified delay (default 2 minutes = 120 seconds)
    logger.info(f"Waiting {delay_seconds} seconds before restarting service {pid}...")
    time.sleep(delay_seconds)
    
    # Start the service
    start_result = monitor.start_service(jar_path)
    if start_result['success']:
        return {
            'success': True,
            'message': 'Service restarted successfully',
            'pid': start_result.get('pid')
        }
    else:
        return {
            'success': False,
            'error': f"Failed to start service: {start_result.get('error')}"
        }


@app.route('/api/service/<int:pid>/restart', methods=['POST'])
def restart_service(pid):
    """Restart a Java JAR service"""
    try:
        data = request.get_json()
        jar_name = data.get('jar_name') if data else None
        
        result = restart_service_internal(pid, jar_name, delay_seconds=120)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result.get('message', 'Service restarted successfully'),
                'pid': result.get('pid')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to restart service')
            }), 400
    except Exception as e:
        logger.error(f"Error restarting service: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/service/<int:pid>/auto-restart', methods=['POST'])
def configure_auto_restart(pid):
    """Configure auto-restart for a service"""
    global auto_restart_config
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        cpu_threshold = data.get('cpu_threshold', 80.0)
        memory_threshold_mb = data.get('memory_threshold_mb', 1000.0)  # Default 1GB
        jar_name = data.get('jar_name')
        
        # Validate CPU threshold (minimum 1% to prevent accidental 0% setting)
        if cpu_threshold < 1 or cpu_threshold > 100:
            return jsonify({
                'success': False,
                'error': 'CPU threshold must be between 1 and 100'
            }), 400
        
        # Validate memory threshold (in MB, reasonable range: 1MB to 10GB)
        if memory_threshold_mb < 1 or memory_threshold_mb > 10240:
            return jsonify({
                'success': False,
                'error': 'Memory threshold must be between 1 MB and 10240 MB (10 GB)'
            }), 400
        
        # Get service name for persistent storage
        service_details = monitor.get_service_details(pid)
        service_name = jar_name or (service_details.get('service_name') if service_details else None) or f'pid_{pid}'
        
        with auto_restart_lock:
            if enabled:
                # Preserve existing config if updating thresholds
                existing_config = auto_restart_config.get(pid, {})
                config_data = {
                    'enabled': True,
                    'cpu_threshold': float(cpu_threshold),
                    'memory_threshold_mb': float(memory_threshold_mb),
                    'jar_name': jar_name or existing_config.get('jar_name'),
                    'restarting': existing_config.get('restarting', False)
                }
                
                # Store in memory (by PID)
                auto_restart_config[pid] = config_data
                
                # Store persistently (by service name, without restarting flag)
                persistent_data = config_data.copy()
                persistent_data.pop('restarting', None)  # Don't persist restarting state
                save_auto_restart_config(service_name, persistent_data)
                
                logger.info(f"Auto-restart configured for PID {pid} ({service_name}): CPU {cpu_threshold}%, Memory {memory_threshold_mb} MB")
            else:
                if pid in auto_restart_config:
                    del auto_restart_config[pid]
                # Remove from persistent storage
                delete_auto_restart_config(service_name)
                logger.info(f"Auto-restart disabled for PID {pid} ({service_name})")
        
        return jsonify({
            'success': True,
            'message': f'Auto-restart {"enabled" if enabled else "disabled"} for service {pid}',
            'config': auto_restart_config.get(pid, {}) if enabled else {}
        })
    except Exception as e:
        logger.error(f"Error configuring auto-restart: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/service/<int:pid>/auto-restart', methods=['GET'])
def get_auto_restart_config(pid):
    """Get auto-restart configuration for a service"""
    global auto_restart_config
    try:
        with auto_restart_lock:
            config = auto_restart_config.get(pid, {
                'enabled': False,
                'cpu_threshold': 80.0,
                'memory_threshold_mb': 1000.0,
                'jar_name': None,
                'restarting': False
            })
        
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        logger.error(f"Error getting auto-restart config: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def auto_restart_monitor():
    """Background thread to monitor CPU and memory utilization and auto-restart services"""
    global auto_restart_config, jar_folder_path
    
    while True:
        try:
            time.sleep(30)  # Check every 30 seconds
            
            with auto_restart_lock:
                configs_to_check = list(auto_restart_config.items())
            
            for pid, config in configs_to_check:
                if not config.get('enabled', False) or config.get('restarting', False):
                    continue
                
                try:
                    details = monitor.get_service_details(pid)
                    if not details:
                        # Service no longer exists, remove from config
                        with auto_restart_lock:
                            if pid in auto_restart_config:
                                del auto_restart_config[pid]
                        continue
                    
                    cpu_percent = details.get('cpu_percent', 0)
                    memory_mb = details.get('memory_mb', 0)
                    cpu_threshold = config.get('cpu_threshold', 80.0)
                    memory_threshold_mb = config.get('memory_threshold_mb', 1000.0)
                    
                    # Check if either CPU or memory threshold is exceeded
                    cpu_exceeded = cpu_percent >= cpu_threshold
                    memory_exceeded = memory_mb >= memory_threshold_mb
                    
                    if cpu_exceeded or memory_exceeded:
                        reason = []
                        if cpu_exceeded:
                            reason.append(f"CPU ({cpu_percent}% >= {cpu_threshold}%)")
                        if memory_exceeded:
                            reason.append(f"Memory ({memory_mb:.1f} MB >= {memory_threshold_mb:.1f} MB)")
                        
                        logger.warning(f"Service {pid} exceeds threshold(s): {', '.join(reason)}. Initiating auto-restart...")
                        
                        # Mark as restarting to prevent multiple restarts
                        with auto_restart_lock:
                            if pid in auto_restart_config:
                                auto_restart_config[pid]['restarting'] = True
                        
                        # Restart in a separate thread to avoid blocking
                        def restart_thread():
                            jar_name = config.get('jar_name')
                            result = restart_service_internal(pid, jar_name, delay_seconds=120)
                            
                            if result['success']:
                                logger.info(f"Auto-restart successful for service {pid}. New PID: {result.get('pid')}")
                                # Update config with new PID if available
                                new_pid = result.get('pid')
                                if new_pid:
                                    with auto_restart_lock:
                                        if pid in auto_restart_config:
                                            old_config = auto_restart_config[pid]
                                            del auto_restart_config[pid]
                                            auto_restart_config[new_pid] = old_config
                                            auto_restart_config[new_pid]['restarting'] = False
                            else:
                                logger.error(f"Auto-restart failed for service {pid}: {result.get('error')}")
                                with auto_restart_lock:
                                    if pid in auto_restart_config:
                                        auto_restart_config[pid]['restarting'] = False
                        
                        threading.Thread(target=restart_thread, daemon=True).start()
                        
                except Exception as e:
                    logger.error(f"Error checking service {pid} for auto-restart: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in auto-restart monitor: {str(e)}")
            time.sleep(60)  # Wait longer on error


if __name__ == '__main__':
    import sys
    
    # Default port, but allow override via command line argument
    port = 5001  # Changed from 5000 to avoid macOS AirPlay Receiver conflict
    
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}. Using default port 5001.")
    
    # Start auto-restart monitoring thread
    monitor_thread = threading.Thread(target=auto_restart_monitor, daemon=True)
    monitor_thread.start()
    logger.info("Auto-restart monitoring thread started")
    
    print("Starting Java JAR Service Monitor...")
    print(f"Access the dashboard at: http://localhost:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)

