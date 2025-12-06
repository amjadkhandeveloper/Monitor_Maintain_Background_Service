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
from msmq_monitor import MSMQMonitor
from config_storage import (
    load_config, save_config, get_auto_restart_config_by_name,
    save_auto_restart_config, delete_auto_restart_config,
    get_folder_path, save_folder_path
)
from constants import (
    DEFAULT_PORT, DEFAULT_CPU_THRESHOLD, DEFAULT_MEMORY_THRESHOLD_MB,
    DEFAULT_QUEUE_THRESHOLD, CPU_THRESHOLD_MIN, CPU_THRESHOLD_MAX,
    MEMORY_THRESHOLD_MIN_MB, MEMORY_THRESHOLD_MAX_MB,
    QUEUE_THRESHOLD_MIN, QUEUE_THRESHOLD_MAX,
    AUTO_RESTART_CHECK_INTERVAL, AUTO_RESTART_ERROR_RETRY_INTERVAL,
    RESTART_DELAY_CPU_MEMORY, RESTART_DELAY_QUEUE,
    SUPPORTED_EXTENSIONS, DASHBOARD_REFRESH_INTERVAL_MS
)
import logging
import platform

app = Flask(__name__)
# SECRET_KEY should be set via environment variable for security
# Example: export FLASK_SECRET_KEY='your-secret-key-here'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'change-this-in-production-use-env-variable')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize service monitor
monitor = ServiceMonitor()

# Initialize MSMQ monitor (Windows only)
msmq_monitor = MSMQMonitor()
msmq_available = msmq_monitor.is_msmq_available()
if msmq_available:
    logger.info("MSMQ monitoring is available")
else:
    logger.info("MSMQ monitoring is not available (Windows-only feature)")

# In-memory cache for auto-restart config (keyed by PID for active processes)
# Persistent storage is in monitor_config.json (keyed by service_name)
auto_restart_config = {}  # {pid: config} - for active processes
auto_restart_lock = threading.Lock()

# Load persistent config on startup
persistent_config = load_config()
jar_folder_path = persistent_config.get('folder_path')

# Load auto-restart configs from persistent storage
logger.info(f"Loaded persistent config: {len(persistent_config.get('auto_restart', {}))} service configurations")


def get_all_executables_from_folder(folder_path):
    """
    Get all executable files from the configured folder.
    Returns both files directly in the folder AND files in subfolders.
    Returns: {
        'executable_name': {
            'executable_path': full_path,
            'executable_name': filename,
            'subfolder_path': subfolder_path or None (None if directly in folder),
            'folder_name': folder_name or None
        }
    }
    """
    executables_map = {}
    
    if not folder_path or not os.path.isdir(folder_path):
        return executables_map
    
    try:
        system = platform.system()
        supported_exts = {
            'Windows': ['.jar', '.exe', '.bat'],
            'Darwin': ['.jar', '.sh'],
            'Linux': ['.jar', '.sh']
        }
        extensions = supported_exts.get(system, ['.jar', '.exe', '.bat', '.sh'])
        
        # Helper function to resolve Windows shortcut target
        def resolve_shortcut(shortcut_path):
            """Resolve Windows shortcut (.lnk) to its target path"""
            if system != 'Windows':
                return None
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(shortcut_path)
                target = shortcut.Targetpath
                return target if target and os.path.exists(target) else None
            except ImportError:
                # Fallback: try using PowerShell
                try:
                    import subprocess
                    ps_command = f'(New-Object -ComObject WScript.Shell).CreateShortcut("{shortcut_path}").TargetPath'
                    result = subprocess.run(
                        ['powershell', '-Command', ps_command],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        target = result.stdout.strip().strip('"')
                        return target if target and os.path.exists(target) else None
                except Exception:
                    pass
            except Exception as e:
                logger.debug(f"Error resolving shortcut {shortcut_path}: {str(e)}")
            return None
        
        # First, scan for files directly in the folder
        direct_files_found = 0
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                file_ext = os.path.splitext(filename)[1].lower()
                
                # Handle Windows shortcuts (.lnk files)
                if file_ext == '.lnk' and system == 'Windows':
                    target_path = resolve_shortcut(file_path)
                    if target_path:
                        target_ext = os.path.splitext(target_path)[1].lower()
                        if target_ext in extensions:
                            # Use shortcut name (without .lnk) as the key
                            file_name_without_ext = os.path.splitext(filename)[0]
                            target_filename = os.path.basename(target_path)
                            executables_map[file_name_without_ext] = {
                                'executable_path': target_path,  # Use actual target path
                                'executable_name': target_filename,  # Use target filename
                                'shortcut_path': file_path,  # Store shortcut path
                                'subfolder_path': os.path.dirname(target_path),  # Target's directory
                                'folder_name': None
                            }
                            direct_files_found += 1
                            logger.debug(f"Found shortcut: {filename} -> {target_path}")
                    continue
                
                # Handle regular executable files
                if file_ext in extensions:
                    file_name_without_ext = os.path.splitext(filename)[0]
                    executables_map[file_name_without_ext] = {
                        'executable_path': file_path,
                        'executable_name': filename,
                        'subfolder_path': None,  # Directly in folder
                        'folder_name': None
                    }
                    direct_files_found += 1
                    logger.debug(f"Found direct executable: {filename} in {folder_path}")
        
        logger.info(f"Found {direct_files_found} executable files directly in folder")
        
        # Then, scan subfolders (for backward compatibility)
        for item_name in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item_name)
            if os.path.isdir(item_path):
                # Look for executable files inside this subfolder
                folder_name_without_ext = os.path.splitext(item_name)[0]
                for filename in os.listdir(item_path):
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext in extensions:
                        file_path = os.path.join(item_path, filename)
                        if os.path.isfile(file_path):
                            file_name_without_ext = os.path.splitext(filename)[0]
                            # Match if filename matches folder name (subfolder structure)
                            # OR add it if it's a direct file in subfolder (for flexibility)
                            if file_name_without_ext.lower() == folder_name_without_ext.lower():
                                # Subfolder structure: folder name matches file name
                                executables_map[file_name_without_ext] = {
                                    'executable_path': file_path,
                                    'executable_name': filename,
                                    'subfolder_path': item_path,
                                    'folder_name': folder_name_without_ext
                                }
                            else:
                                # Direct file in subfolder: use filename as key
                                executables_map[file_name_without_ext] = {
                                    'executable_path': file_path,
                                    'executable_name': filename,
                                    'subfolder_path': item_path,
                                    'folder_name': folder_name_without_ext
                                }
    except Exception as e:
        logger.error(f"Error scanning folder for executables: {str(e)}", exc_info=True)
    
    logger.info(f"Total executables found: {len(executables_map)} (direct files + subfolders)")
    return executables_map


@app.route('/')
def index():
    """Main dashboard page"""
    # Pass constants to template
    return render_template('dashboard.html',
                         refresh_interval_ms=DASHBOARD_REFRESH_INTERVAL_MS,
                         default_cpu_threshold=DEFAULT_CPU_THRESHOLD,
                         default_memory_threshold_mb=DEFAULT_MEMORY_THRESHOLD_MB,
                         default_queue_threshold=DEFAULT_QUEUE_THRESHOLD,
                         cpu_threshold_min=CPU_THRESHOLD_MIN,
                         cpu_threshold_max=CPU_THRESHOLD_MAX,
                         memory_threshold_min_mb=MEMORY_THRESHOLD_MIN_MB,
                         memory_threshold_max_mb=MEMORY_THRESHOLD_MAX_MB,
                         queue_threshold_min=QUEUE_THRESHOLD_MIN,
                         queue_threshold_max=QUEUE_THRESHOLD_MAX)


@app.route('/api/services', methods=['GET'])
def get_services():
    """Get list of all Java JAR services with their status and utilization"""
    global auto_restart_config, jar_folder_path
    try:
        # Get all running services
        all_services = monitor.get_all_services()
        logger.info(f"Found {len(all_services)} total running services (JAR/EXE/BAT/SH)")
        
        # Get all executables from configured folder (both direct files and subfolders)
        folder_executables_map = get_all_executables_from_folder(jar_folder_path)
        logger.info(f"Found {len(folder_executables_map)} executables in folder '{jar_folder_path}': {list(folder_executables_map.keys())}")
        
        # Build a set of executable names and paths to filter by
        # We'll match services to these executables
        executable_names = set()
        executable_paths = set()
        executable_names_to_info = {}  # {executable_name: info}
        
        for exe_name, exe_info in folder_executables_map.items():
            executable_names.add(exe_name.lower())
            executable_names.add(exe_info['executable_name'].lower())
            executable_paths.add(os.path.normpath(exe_info['executable_path']).lower())
            executable_names_to_info[exe_name.lower()] = exe_info
            executable_names_to_info[exe_info['executable_name'].lower()] = exe_info
        
        # Filter services to only include those matching executables in the folder
        # Match by executable filename (not path) so services run from different locations are still detected
        services = []
        for service in all_services:
            service_name = service.get('service_name') or service.get('jar_name', 'Unknown')
            service_path = service.get('service_path') or service.get('jar_path', '')
            
            # Extract just the filename from service_path (if it's a full path)
            service_filename = service_name
            if service_path:
                # Try to extract filename from path
                if os.path.sep in service_path or '\\' in service_path:
                    service_filename_from_path = os.path.basename(service_path)
                    if service_filename_from_path:
                        service_filename = service_filename_from_path
            
            # Normalize for comparison
            service_filename_lower = service_filename.lower()
            service_filename_no_ext = os.path.splitext(service_filename_lower)[0]
            service_name_lower = service_name.lower()
            service_name_no_ext = os.path.splitext(service_name_lower)[0]
            service_path_normalized = os.path.normpath(service_path).lower() if service_path else ''
            
            # Match by executable filename (regardless of execution path):
            # 1. Service filename (from path or name) matches executable name
            # 2. Service filename without extension matches executable name without extension
            # 3. Service name matches executable name
            # 4. Service path matches executable path (exact match)
            matches = False
            
            # Check if any executable filename matches this service's filename
            for exe_name, exe_info in folder_executables_map.items():
                exe_filename = exe_info['executable_name']
                exe_filename_lower = exe_filename.lower()
                exe_filename_no_ext = os.path.splitext(exe_filename_lower)[0]
                exe_name_lower = exe_name.lower()
                
                # Match by filename (most important - works regardless of execution path)
                if (service_filename_lower == exe_filename_lower or
                    service_filename_no_ext == exe_filename_no_ext or
                    service_filename_no_ext == exe_name_lower or
                    service_name_lower == exe_filename_lower or
                    service_name_no_ext == exe_filename_no_ext or
                    service_name_no_ext == exe_name_lower):
                    matches = True
                    logger.debug(f"Matched service '{service_name}' (filename: '{service_filename}') to executable '{exe_filename}' in folder")
                    break
            
            # Also check path match (for services executed from the configured folder)
            if not matches:
                if service_path_normalized in executable_paths:
                    matches = True
                elif service_path_normalized:
                    for exe_path in executable_paths:
                        if exe_path in service_path_normalized or service_path_normalized in exe_path:
                            matches = True
                            break
            
            if matches:
                services.append(service)
                logger.debug(f"✓ Matched service '{service_name}' (filename: '{service_filename}', path: '{service_path}')")
            else:
                logger.debug(f"✗ Service '{service_name}' (filename: '{service_filename}', path: '{service_path}') did not match any executable in folder")
        
        logger.info(f"Filtered to {len(services)} services matching executables in folder '{jar_folder_path}'")
        
        # Get MSMQ queue information (Windows only)
        queues_info = {}
        all_queues_list = []  # Store all queues for display even if not matched
        if msmq_available and platform.system() == 'Windows':
            try:
                all_queues = msmq_monitor.get_all_queues()
                all_queues_list = all_queues  # Store for potential display
                
                for queue in all_queues:
                    queue_name = queue.get('Name', '')
                    message_count = queue.get('MessageCount', 0)
                    queue_type = queue.get('QueueType', 'Unknown')
                    
                    # Extract simple queue name using improved method
                    queue_simple_name = msmq_monitor.extract_queue_simple_name(queue_name)
                    queue_simple_name_no_ext = os.path.splitext(queue_simple_name)[0].lower()
                    
                    # Match queue name to executable name (case-insensitive)
                    matched_executable = None
                    for exe_name, exe_info in folder_executables_map.items():
                        exe_name_lower = exe_name.lower()
                        exe_name_no_ext = os.path.splitext(exe_info['executable_name'])[0].lower()
                        exe_file_name = exe_info['executable_name']
                        
                        # Try multiple matching strategies
                        if (exe_name_lower == queue_simple_name_no_ext or 
                            exe_name_no_ext == queue_simple_name_no_ext or
                            exe_file_name.lower() == queue_simple_name.lower() or
                            os.path.splitext(exe_file_name)[0].lower() == queue_simple_name_no_ext):
                            matched_executable = exe_info
                            logger.debug(f"Matched queue '{queue_name}' to executable '{exe_file_name}'")
                            break
                    
                    if matched_executable:
                        exe_name = matched_executable['executable_name']
                        queues_info[exe_name] = {
                            'queue_name': queue_name,
                            'message_count': message_count,
                            'queue_type': queue_type,
                            'executable_path': matched_executable['executable_path'],
                            'subfolder_path': matched_executable.get('subfolder_path'),
                            'folder_name': matched_executable.get('folder_name'),
                            'queue_simple_name': queue_simple_name
                        }
                    else:
                        logger.debug(f"No match found for queue '{queue_name}' (simple name: '{queue_simple_name_no_ext}')")
            except Exception as e:
                logger.error(f"Error getting MSMQ queues: {str(e)}", exc_info=True)
        
        # Add auto-restart configuration and MSMQ info to each service
        # First check in-memory (by PID), then check persistent storage (by service name)
        with auto_restart_lock:
            for service in services:
                pid = service['pid']
                service_name = service.get('service_name') or service.get('jar_name', 'Unknown')
                service_path = service.get('service_path') or service.get('jar_path', '')
                
                # Match MSMQ queue to service by multiple methods:
                # 1. Match by service name (executable name)
                # 2. Match by service path (full executable path)
                # 3. Match by folder name (if service path contains a known folder)
                matched_queue = None
                
                # Method 1: Direct name match
                if service_name in queues_info:
                    matched_queue = queues_info[service_name]
                else:
                    # Method 2: Match by service path
                    if service_path:
                        # Normalize paths for comparison
                        service_path_normalized = os.path.normpath(service_path).lower()
                        for exe_name, queue_info in queues_info.items():
                            exe_path_normalized = os.path.normpath(queue_info.get('executable_path', '')).lower()
                            if service_path_normalized == exe_path_normalized:
                                matched_queue = queue_info
                                break
                        
                        # Method 3: Match by folder name (extract folder from path)
                        if not matched_queue:
                            # Try to match by folder name from service path
                            for exe_name, exe_info in folder_executables_map.items():
                                if exe_info.get('subfolder_path'):
                                    folder_path_normalized = os.path.normpath(exe_info['subfolder_path']).lower()
                                    if folder_path_normalized in service_path_normalized:
                                        # Found matching folder, now find its queue
                                        exe_file_name = exe_info['executable_name']
                                        if exe_file_name in queues_info:
                                            matched_queue = queues_info[exe_file_name]
                                            break
                
                service['msmq_queue'] = matched_queue
                
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
                            'cpu_threshold': DEFAULT_CPU_THRESHOLD,
                            'memory_threshold_mb': DEFAULT_MEMORY_THRESHOLD_MB,
                            'queue_threshold': DEFAULT_QUEUE_THRESHOLD,
                            'restarting': False
                        }
        
        return jsonify({
            'success': True,
            'services': services,
            'msmq_available': msmq_available,
            'all_queues': all_queues_list if msmq_available else []  # Include all queues for debugging/display
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
    """Start a Java JAR service (requires jar_path in request body, optionally working_directory)"""
    try:
        data = request.get_json()
        jar_path = data.get('jar_path') if data else None
        working_directory = data.get('working_directory') if data else None
        
        if not jar_path:
            return jsonify({
                'success': False,
                'error': 'jar_path is required'
            }), 400
        
        result = monitor.start_service(jar_path, working_directory=working_directory)
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


@app.route('/api/folder/get', methods=['GET'])
def get_folder_path():
    """Get the current folder path"""
    global jar_folder_path
    try:
        # Try to get from memory first, then from persistent storage
        if jar_folder_path:
            return jsonify({
                'success': True,
                'folder_path': jar_folder_path
            })
        
        # Load from persistent storage
        saved_path = get_folder_path()
        if saved_path:
            jar_folder_path = saved_path
            return jsonify({
                'success': True,
                'folder_path': saved_path
            })
        
        return jsonify({
            'success': True,
            'folder_path': None
        })
    except Exception as e:
        logger.error(f"Error getting folder path: {str(e)}")
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
        
        # Get all executables using the helper function
        executables_map = get_all_executables_from_folder(folder)
        
        # Organize into structure: direct files and subfolders
        direct_files = []
        subfolders_with_executables = []
        
        try:
            # First, get direct files in the folder
            for exe_name, exe_info in executables_map.items():
                if exe_info['subfolder_path'] is None:
                    # Direct file in folder
                    file_size = os.path.getsize(exe_info['executable_path'])
                    file_ext = os.path.splitext(exe_info['executable_name'])[1].lower()
                    file_type = file_ext.upper().replace('.', '')
                    direct_files.append({
                        'name': exe_info['executable_name'],
                        'path': exe_info['executable_path'],
                        'subfolder_path': None,
                        'size_mb': round(file_size / (1024 * 1024), 2),
                        'type': file_type,
                        'extension': file_ext
                    })
            
            # Then, organize subfolder files
            subfolder_map = {}  # {subfolder_path: {folder_name, executables}}
            for exe_name, exe_info in executables_map.items():
                if exe_info['subfolder_path']:
                    subfolder_path = exe_info['subfolder_path']
                    if subfolder_path not in subfolder_map:
                        folder_name = os.path.basename(subfolder_path)
                        subfolder_map[subfolder_path] = {
                            'folder_name': folder_name,
                            'folder_path': subfolder_path,
                            'executables': []
                        }
                    
                    file_size = os.path.getsize(exe_info['executable_path'])
                    file_ext = os.path.splitext(exe_info['executable_name'])[1].lower()
                    file_type = file_ext.upper().replace('.', '')
                    subfolder_map[subfolder_path]['executables'].append({
                        'name': exe_info['executable_name'],
                        'path': exe_info['executable_path'],
                        'subfolder_path': subfolder_path,
                        'size_mb': round(file_size / (1024 * 1024), 2),
                        'type': file_type,
                        'extension': file_ext
                    })
            
            # Convert subfolder map to list
            subfolders_with_executables = list(subfolder_map.values())
            
            # Sort both lists
            direct_files.sort(key=lambda x: x['name'])
            subfolders_with_executables.sort(key=lambda x: x['folder_name'])
            
        except PermissionError:
            return jsonify({
                'success': False,
                'error': f'Permission denied accessing folder: {folder}'
            }), 403
        except Exception as e:
            logger.error(f"Error organizing executables: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        
        return jsonify({
            'success': True,
            'direct_files': direct_files,  # Files directly in folder
            'subfolders': subfolders_with_executables,  # Files in subfolders
            'folder_path': folder
        })
    except Exception as e:
        logger.error(f"Error listing JAR files: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def restart_service_internal(pid, jar_name=None, delay_seconds=RESTART_DELAY_CPU_MEMORY, working_directory=None):
    """Internal function to restart a service with configurable delay"""
    global jar_folder_path
    
    # Determine jar_path: use jar_name + folder_path if provided, otherwise use existing jar_path
    jar_path = None
    working_dir = working_directory
    
    if jar_name and jar_folder_path:
        # Search in subfolders: look for subfolder matching jar_name, then find executable inside
        jar_name_without_ext = os.path.splitext(jar_name)[0]
        
        # Check if main folder has subfolders
        if os.path.isdir(jar_folder_path):
            for item_name in os.listdir(jar_folder_path):
                item_path = os.path.join(jar_folder_path, item_name)
                if os.path.isdir(item_path):
                    # Check if folder name matches jar_name (without extension)
                    folder_name_without_ext = os.path.splitext(item_name)[0]
                    if folder_name_without_ext.lower() == jar_name_without_ext.lower():
                        # Found matching subfolder, look for executable inside
                        system = platform.system()
                        extensions = SUPPORTED_EXTENSIONS.get(system, ['.jar', '.exe', '.bat', '.sh'])
                        for filename in os.listdir(item_path):
                            file_ext = os.path.splitext(filename)[1].lower()
                            if file_ext in extensions:
                                file_path = os.path.join(item_path, filename)
                                file_name_without_ext = os.path.splitext(filename)[0]
                                if file_name_without_ext.lower() == jar_name_without_ext.lower():
                                    jar_path = file_path
                                    working_dir = item_path  # Use subfolder as working directory
                                    break
                        if jar_path:
                            break
        
        # Fallback: try direct path in main folder (backward compatibility)
        if not jar_path:
            jar_path = os.path.join(jar_folder_path, jar_name)
            jar_path = os.path.normpath(jar_path)
        
        if not jar_path or not os.path.exists(jar_path):
            return {
                'success': False,
                'error': f'Executable file not found for: {jar_name}. Searched in subfolders of {jar_folder_path}'
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
                'error': 'Could not determine executable path for service. Please set folder path and provide jar_name.'
            }
        
        # Try to determine working directory from jar_path
        if not working_dir and jar_path:
            # If jar_path is in a subfolder, use that subfolder as working directory
            if jar_folder_path and jar_path.startswith(jar_folder_path):
                # Check if it's in a subfolder
                relative_path = os.path.relpath(jar_path, jar_folder_path)
                if os.path.sep in relative_path:
                    # It's in a subfolder
                    subfolder = os.path.join(jar_folder_path, relative_path.split(os.path.sep)[0])
                    if os.path.isdir(subfolder):
                        working_dir = subfolder
    
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
    
    # Start the service with working directory
    start_result = monitor.start_service(jar_path, working_directory=working_dir)
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
        
        result = restart_service_internal(pid, jar_name, delay_seconds=RESTART_DELAY_CPU_MEMORY)
        
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
        cpu_threshold = data.get('cpu_threshold', DEFAULT_CPU_THRESHOLD)
        memory_threshold_mb = data.get('memory_threshold_mb', DEFAULT_MEMORY_THRESHOLD_MB)
        jar_name = data.get('jar_name')
        
        # Validate CPU threshold
        if cpu_threshold < CPU_THRESHOLD_MIN or cpu_threshold > CPU_THRESHOLD_MAX:
            return jsonify({
                'success': False,
                'error': f'CPU threshold must be between {CPU_THRESHOLD_MIN} and {CPU_THRESHOLD_MAX}'
            }), 400
        
        # Validate memory threshold
        if memory_threshold_mb < MEMORY_THRESHOLD_MIN_MB or memory_threshold_mb > MEMORY_THRESHOLD_MAX_MB:
            return jsonify({
                'success': False,
                'error': f'Memory threshold must be between {MEMORY_THRESHOLD_MIN_MB} MB and {MEMORY_THRESHOLD_MAX_MB} MB (10 GB)'
            }), 400
        
        # Get queue threshold
        queue_threshold = data.get('queue_threshold', DEFAULT_QUEUE_THRESHOLD)
        if queue_threshold < QUEUE_THRESHOLD_MIN or queue_threshold > QUEUE_THRESHOLD_MAX:
            return jsonify({
                'success': False,
                'error': 'Queue threshold must be between 1 and 1,000,000 messages'
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
                    'queue_threshold': int(queue_threshold),
                    'jar_name': jar_name or existing_config.get('jar_name'),
                    'restarting': existing_config.get('restarting', False)
                }
                
                # Store in memory (by PID)
                auto_restart_config[pid] = config_data
                
                # Store persistently (by service name, without restarting flag)
                persistent_data = config_data.copy()
                persistent_data.pop('restarting', None)  # Don't persist restarting state
                save_auto_restart_config(service_name, persistent_data)
                
                logger.info(f"Auto-restart configured for PID {pid} ({service_name}): CPU {cpu_threshold}%, Memory {memory_threshold_mb} MB, Queue {queue_threshold} messages")
            else:
                # When disabling, preserve queue_threshold if it exists (queue monitoring is independent)
                existing_config = auto_restart_config.get(pid, {})
                existing_queue_threshold = existing_config.get('queue_threshold')
                
                if pid in auto_restart_config:
                    # If queue threshold exists, keep minimal config for queue monitoring
                    if existing_queue_threshold:
                        auto_restart_config[pid] = {
                            'enabled': False,  # CPU/Memory auto-restart disabled
                            'queue_threshold': existing_queue_threshold,
                            'jar_name': jar_name or existing_config.get('jar_name'),
                            'restarting': False
                        }
                        # Save queue threshold to persistent storage
                        persistent_data = {
                            'enabled': False,
                            'queue_threshold': existing_queue_threshold,
                            'jar_name': jar_name or existing_config.get('jar_name')
                        }
                        save_auto_restart_config(service_name, persistent_data)
                    else:
                        del auto_restart_config[pid]
                        delete_auto_restart_config(service_name)
                else:
                    # Remove from persistent storage only if no queue threshold
                    if not existing_queue_threshold:
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
                'cpu_threshold': DEFAULT_CPU_THRESHOLD,
                'memory_threshold_mb': DEFAULT_MEMORY_THRESHOLD_MB,
                'queue_threshold': DEFAULT_QUEUE_THRESHOLD,
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


@app.route('/api/service/<int:pid>/queue-threshold', methods=['POST'])
def set_queue_threshold(pid):
    """Set queue threshold independently (works even if CPU/Memory auto-restart is disabled)"""
    global auto_restart_config
    try:
        data = request.get_json()
        queue_threshold = data.get('queue_threshold', DEFAULT_QUEUE_THRESHOLD)
        jar_name = data.get('jar_name')
        
        if queue_threshold < QUEUE_THRESHOLD_MIN or queue_threshold > QUEUE_THRESHOLD_MAX:
            return jsonify({
                'success': False,
                'error': f'Queue threshold must be between {QUEUE_THRESHOLD_MIN} and {QUEUE_THRESHOLD_MAX:,} messages'
            }), 400
        
        # Get service name for persistent storage
        service_details = monitor.get_service_details(pid)
        service_name = jar_name or (service_details.get('service_name') if service_details else None) or f'pid_{pid}'
        
        with auto_restart_lock:
            existing_config = auto_restart_config.get(pid, {})
            
            # Preserve existing CPU/Memory settings if they exist
            config_data = {
                'enabled': existing_config.get('enabled', False),  # Keep existing enabled state
                'cpu_threshold': existing_config.get('cpu_threshold', DEFAULT_CPU_THRESHOLD),
                'memory_threshold_mb': existing_config.get('memory_threshold_mb', DEFAULT_MEMORY_THRESHOLD_MB),
                'queue_threshold': int(queue_threshold),
                    'jar_name': jar_name or existing_config.get('jar_name'),
                    'restarting': existing_config.get('restarting', False)
                }
            
            # Store in memory (by PID)
            auto_restart_config[pid] = config_data
            
            # Store persistently (by service name, without restarting flag)
            persistent_data = config_data.copy()
            persistent_data.pop('restarting', None)  # Don't persist restarting state
            save_auto_restart_config(service_name, persistent_data)
            
            logger.info(f"Queue threshold set for PID {pid} ({service_name}): {queue_threshold} messages")
        
        return jsonify({
            'success': True,
            'message': f'Queue threshold set to {queue_threshold} messages',
            'config': config_data
        })
    except Exception as e:
        logger.error(f"Error setting queue threshold: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/msmq/queues', methods=['GET'])
def get_msmq_queues():
    """Get all MSMQ queues with their message counts"""
    global jar_folder_path
    
    if not msmq_available:
        return jsonify({
            'success': False,
            'error': 'MSMQ monitoring is only available on Windows',
            'msmq_available': False
        }), 400
    
    try:
        # Get executable files for matching
        executable_files = []
        if jar_folder_path and os.path.isdir(jar_folder_path):
            try:
                system = platform.system()
                supported_exts = {
                    'Windows': ['.jar', '.exe', '.bat'],
                    'Darwin': ['.jar', '.sh'],
                    'Linux': ['.jar', '.sh']
                }
                extensions = supported_exts.get(system, ['.jar', '.exe', '.bat', '.sh'])
                
                for filename in os.listdir(jar_folder_path):
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext in extensions:
                        file_path = os.path.join(jar_folder_path, filename)
                        if os.path.isfile(file_path):
                            executable_files.append(file_path)
            except Exception as e:
                logger.warning(f"Error getting executable files: {str(e)}")
        
        # Get all queues
        all_queues = msmq_monitor.get_all_queues()
        
        # Match queues to executables
        queues_with_matches = []
        for queue in all_queues:
            queue_name = queue.get('Name', '')
            message_count = queue.get('MessageCount', 0)
            matched_exe = msmq_monitor.match_queue_to_executable(queue_name, executable_files)
            
            queue_info = {
                'queue_name': queue_name,
                'message_count': message_count,
                'queue_type': queue.get('QueueType', 'Unknown'),
                'path': queue.get('Path', ''),
                'matched_executable': os.path.basename(matched_exe) if matched_exe else None,
                'executable_path': matched_exe if matched_exe else None
            }
            queues_with_matches.append(queue_info)
        
        return jsonify({
            'success': True,
            'queues': queues_with_matches,
            'msmq_available': True
        })
    except Exception as e:
        logger.error(f"Error getting MSMQ queues: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'msmq_available': True
        }), 500


def auto_restart_monitor():
    """Background thread to monitor CPU, memory utilization, and MSMQ queue counts, then auto-restart services"""
    global auto_restart_config, jar_folder_path
    
    while True:
        try:
            time.sleep(AUTO_RESTART_CHECK_INTERVAL)  # Check every 30 seconds
            
            # Get all executables from folder using helper function
            folder_executables_map = get_all_executables_from_folder(jar_folder_path)
            
            # Get MSMQ queue information (Windows only)
            queue_message_counts = {}  # {executable_name: message_count}
            queue_folder_map = {}  # {executable_name: subfolder_path} for restart
            if msmq_available and platform.system() == 'Windows':
                try:
                    all_queues = msmq_monitor.get_all_queues()
                    logger.debug(f"Found {len(all_queues)} MSMQ queues")
                    
                    for queue in all_queues:
                        queue_name = queue.get('Name', '')
                        message_count = queue.get('MessageCount', 0)
                        queue_type = queue.get('QueueType', 'Unknown')
                        
                        # Extract simple queue name using improved method
                        queue_simple_name = msmq_monitor.extract_queue_simple_name(queue_name)
                        queue_simple_name_no_ext = os.path.splitext(queue_simple_name)[0].lower()
                        
                        logger.debug(f"Processing queue: '{queue_name}' -> simple name: '{queue_simple_name}' -> no ext: '{queue_simple_name_no_ext}', messages: {message_count}")
                        
                        # Match queue name to executable name
                        matched = False
                        for exe_name, exe_info in folder_executables_map.items():
                            exe_name_lower = exe_name.lower()
                            exe_name_no_ext = os.path.splitext(exe_info['executable_name'])[0].lower()
                            exe_file_name = exe_info['executable_name']
                            
                            # Try multiple matching strategies
                            if (exe_name_lower == queue_simple_name_no_ext or 
                                exe_name_no_ext == queue_simple_name_no_ext or
                                exe_file_name.lower() == queue_simple_name.lower() or
                                os.path.splitext(exe_file_name)[0].lower() == queue_simple_name_no_ext):
                                
                                queue_message_counts[exe_file_name] = message_count
                                queue_folder_map[exe_file_name] = exe_info.get('subfolder_path')
                                logger.info(f"Matched MSMQ queue '{queue_name}' ({queue_type}, {message_count} messages) to executable '{exe_file_name}'")
                                matched = True
                                break
                        
                        if not matched:
                            logger.debug(f"No match found for queue '{queue_name}' (simple name: '{queue_simple_name_no_ext}')")
                            
                except Exception as e:
                    logger.error(f"Error getting MSMQ queues in monitor: {str(e)}", exc_info=True)
            
            # Get all running services and filter to only those in our folder
            all_running_services = monitor.get_all_services()
            
            # Build filter set from folder executables
            executable_names = set()
            executable_paths = set()
            for exe_name, exe_info in folder_executables_map.items():
                executable_names.add(exe_name.lower())
                executable_names.add(exe_info['executable_name'].lower())
                executable_paths.add(os.path.normpath(exe_info['executable_path']).lower())
            
            # Filter services to only include those matching executables in the folder
            # Match by executable filename (not path) so services run from different locations are still detected
            running_services = []
            for service in all_running_services:
                service_name = service.get('service_name') or service.get('jar_name', 'Unknown')
                service_path = service.get('service_path') or service.get('jar_path', '')
                
                # Extract just the filename from service_path (if it's a full path)
                service_filename = service_name
                if service_path:
                    if os.path.sep in service_path or '\\' in service_path:
                        service_filename_from_path = os.path.basename(service_path)
                        if service_filename_from_path:
                            service_filename = service_filename_from_path
                
                # Normalize for comparison
                service_filename_lower = service_filename.lower()
                service_filename_no_ext = os.path.splitext(service_filename_lower)[0]
                service_name_lower = service_name.lower()
                service_name_no_ext = os.path.splitext(service_name_lower)[0]
                service_path_normalized = os.path.normpath(service_path).lower() if service_path else ''
                
                matches = False
                
                # Check if any executable filename matches this service's filename
                for exe_name, exe_info in folder_executables_map.items():
                    exe_filename = exe_info['executable_name']
                    exe_filename_lower = exe_filename.lower()
                    exe_filename_no_ext = os.path.splitext(exe_filename_lower)[0]
                    exe_name_lower = exe_name.lower()
                    
                    # Match by filename (most important - works regardless of execution path)
                    if (service_filename_lower == exe_filename_lower or
                        service_filename_no_ext == exe_filename_no_ext or
                        service_filename_no_ext == exe_name_lower or
                        service_name_lower == exe_filename_lower or
                        service_name_no_ext == exe_filename_no_ext or
                        service_name_no_ext == exe_name_lower):
                        matches = True
                        break
                
                # Also check path match (for services executed from the configured folder)
                if not matches:
                    if service_path_normalized in executable_paths:
                        matches = True
                    elif service_path_normalized:
                        for exe_path in executable_paths:
                            if exe_path in service_path_normalized or service_path_normalized in exe_path:
                                matches = True
                                break
                
                if matches:
                    running_services.append(service)
            service_by_name = {}
            for service in running_services:
                service_name = service.get('service_name') or service.get('jar_name', 'Unknown')
                service_by_name[service_name] = service
            
            # FIRST: Check MSMQ queues independently for ALL services (regardless of auto-restart setting)
            # This is an additional condition that works independently
            if msmq_available and platform.system() == 'Windows' and queue_message_counts:
                for service in running_services:
                    pid = service['pid']
                    service_name = service.get('service_name') or service.get('jar_name', 'Unknown')
                    
                    # Skip if already restarting
                    with auto_restart_lock:
                        existing_config = auto_restart_config.get(pid, {})
                        if existing_config.get('restarting', False):
                            continue
                    
                    # Check if this service has a queue with exceeded threshold
                    if service_name in queue_message_counts:
                        queue_message_count = queue_message_counts[service_name]
                        # Use default threshold of 1,000 if not configured, or get from config if exists
                        queue_threshold = existing_config.get('queue_threshold', DEFAULT_QUEUE_THRESHOLD)
                        
                        logger.debug(f"Service {pid} ({service_name}): Queue message count = {queue_message_count}, threshold = {queue_threshold}")
                        
                        if queue_message_count >= queue_threshold:
                            logger.warning(f"Service {pid} ({service_name}) MSMQ queue exceeds threshold: {queue_message_count} >= {queue_threshold} messages. Initiating auto-restart...")
                            
                            # Mark as restarting
                            with auto_restart_lock:
                                if pid not in auto_restart_config:
                                    # Create minimal config for queue-based restart
                                    auto_restart_config[pid] = {
                                        'enabled': False,  # Queue monitoring is independent
                                        'queue_threshold': queue_threshold,
                                        'jar_name': service_name,
                                        'restarting': True
                                    }
                                else:
                                    auto_restart_config[pid]['restarting'] = True
                            
                            # Restart in a separate thread
                            def queue_restart_thread():
                                jar_name = service_name
                                # Get the subfolder path for this service from the map
                                subfolder_path = queue_folder_map.get(service_name)
                                result = restart_service_internal(pid, jar_name, delay_seconds=RESTART_DELAY_QUEUE, working_directory=subfolder_path)
                                
                                if result['success']:
                                    logger.info(f"Queue-based auto-restart successful for service {pid} ({service_name}). New PID: {result.get('pid')}")
                                    new_pid = result.get('pid')
                                    if new_pid:
                                        with auto_restart_lock:
                                            if pid in auto_restart_config:
                                                old_config = auto_restart_config[pid]
                                                del auto_restart_config[pid]
                                                # Only keep queue threshold if it was set
                                                if old_config.get('queue_threshold'):
                                                    auto_restart_config[new_pid] = {
                                                        'enabled': old_config.get('enabled', False),
                                                        'queue_threshold': old_config['queue_threshold'],
                                                        'jar_name': jar_name,
                                                        'restarting': False
                                                    }
                                else:
                                    logger.error(f"Queue-based auto-restart failed for service {pid} ({service_name}): {result.get('error')}")
                                    with auto_restart_lock:
                                        if pid in auto_restart_config:
                                            auto_restart_config[pid]['restarting'] = False
                            
                            threading.Thread(target=queue_restart_thread, daemon=True).start()
                            continue  # Skip to next service
            
            # SECOND: Check CPU and Memory thresholds for services with auto-restart enabled
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
                    
                    service_name = details.get('service_name') or details.get('jar_name', 'Unknown')
                    cpu_percent = details.get('cpu_percent', 0)
                    memory_mb = details.get('memory_mb', 0)
                    cpu_threshold = config.get('cpu_threshold', DEFAULT_CPU_THRESHOLD)
                    memory_threshold_mb = config.get('memory_threshold_mb', DEFAULT_MEMORY_THRESHOLD_MB)
                    
                    # Check CPU and memory thresholds
                    cpu_exceeded = cpu_percent >= cpu_threshold
                    memory_exceeded = memory_mb >= memory_threshold_mb
                    
                    # Check MSMQ queue threshold (only if auto-restart is enabled)
                    queue_threshold = config.get('queue_threshold', DEFAULT_QUEUE_THRESHOLD)
                    queue_exceeded = False
                    queue_message_count = None
                    
                    if service_name in queue_message_counts:
                        queue_message_count = queue_message_counts[service_name]
                        queue_exceeded = queue_message_count >= queue_threshold
                    
                    # Check if any threshold is exceeded (CPU, Memory, or Queue)
                    if cpu_exceeded or memory_exceeded or queue_exceeded:
                        reason = []
                        if cpu_exceeded:
                            reason.append(f"CPU ({cpu_percent}% >= {cpu_threshold}%)")
                        if memory_exceeded:
                            reason.append(f"Memory ({memory_mb:.1f} MB >= {memory_threshold_mb:.1f} MB)")
                        if queue_exceeded:
                            reason.append(f"MSMQ Queue ({queue_message_count} >= {queue_threshold} messages)")
                        
                        logger.warning(f"Service {pid} ({service_name}) exceeds threshold(s): {', '.join(reason)}. Initiating auto-restart...")
                        
                        # Mark as restarting to prevent multiple restarts
                        with auto_restart_lock:
                            if pid in auto_restart_config:
                                auto_restart_config[pid]['restarting'] = True
                        
                        # Restart in a separate thread to avoid blocking
                        def restart_thread():
                            jar_name = config.get('jar_name')
                            # Use queue delay for queue-based restarts, CPU/memory delay for CPU/memory
                            delay = RESTART_DELAY_QUEUE if queue_exceeded else RESTART_DELAY_CPU_MEMORY
                            # Get subfolder path for this service
                            subfolder_path = None
                            if jar_name:
                                for exe_name, exe_info in folder_executables_map.items():
                                    if exe_info['executable_name'] == jar_name or exe_name == jar_name:
                                        subfolder_path = exe_info.get('subfolder_path')
                                        break
                            result = restart_service_internal(pid, jar_name, delay_seconds=delay, working_directory=subfolder_path)
                            
                            if result['success']:
                                logger.info(f"Auto-restart successful for service {pid} ({service_name}). New PID: {result.get('pid')}")
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
                                logger.error(f"Auto-restart failed for service {pid} ({service_name}): {result.get('error')}")
                                with auto_restart_lock:
                                    if pid in auto_restart_config:
                                        auto_restart_config[pid]['restarting'] = False
                        
                        threading.Thread(target=restart_thread, daemon=True).start()
                        
                except Exception as e:
                    logger.error(f"Error checking service {pid} for auto-restart: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in auto-restart monitor: {str(e)}")
            time.sleep(AUTO_RESTART_ERROR_RETRY_INTERVAL)  # Wait longer on error


if __name__ == '__main__':
    import sys
    
    # Default port, but allow override via command line argument
    port = DEFAULT_PORT
    
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}. Using default port {DEFAULT_PORT}.")
    
    # Start auto-restart monitoring thread
    monitor_thread = threading.Thread(target=auto_restart_monitor, daemon=True)
    monitor_thread.start()
    logger.info("Auto-restart monitoring thread started")
    
    print("Starting Java JAR Service Monitor...")
    print(f"Access the dashboard at: http://localhost:{port}")
    # Debug mode disabled for production (set debug=False or use environment variable)
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)

