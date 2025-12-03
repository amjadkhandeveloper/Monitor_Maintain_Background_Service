"""
Service Monitor Module
Handles detection, monitoring, and control of services (JAR, EXE, BAT, SH) on Windows, macOS, and Linux
"""

import psutil
import subprocess
import os
import platform
import logging
from datetime import datetime
import json
import stat

logger = logging.getLogger(__name__)

# Supported file extensions by OS
SUPPORTED_EXTENSIONS = {
    'Windows': ['.jar', '.exe', '.bat'],
    'Darwin': ['.jar', '.sh'],  # macOS
    'Linux': ['.jar', '.sh']
}


class ServiceMonitor:
    """Monitor and control services (JAR, EXE, BAT, SH files)"""
    
    def __init__(self):
        """Initialize the service monitor"""
        self.processes = []
        self.system = platform.system()
    
    def _get_supported_extensions(self):
        """Get supported file extensions for current OS"""
        return SUPPORTED_EXTENSIONS.get(self.system, ['.jar', '.exe', '.bat', '.sh'])
    
    def _is_service_process(self, process):
        """Check if a process is a monitored service (JAR, EXE, BAT, SH)"""
        try:
            cmdline = process.cmdline()
            if not cmdline:
                return False
            
            exe_path = cmdline[0].lower()
            
            # Check for Java JAR processes
            if 'java' in exe_path or 'javaw' in exe_path:
                for arg in cmdline:
                    if arg.endswith('.jar'):
                        return True
            
            # Check for executable files (.exe, .bat, .sh)
            for ext in ['.exe', '.bat', '.sh']:
                if exe_path.endswith(ext) or any(arg.endswith(ext) for arg in cmdline):
                    return True
            
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    
    def _get_service_path(self, process):
        """Extract service file path from process command line"""
        try:
            cmdline = process.cmdline()
            exe_path = cmdline[0]
            
            # Check for JAR files
            for arg in cmdline:
                if arg.endswith('.jar'):
                    return arg
            
            # Check for executable files
            for ext in ['.exe', '.bat', '.sh']:
                if exe_path.endswith(ext):
                    return exe_path
                for arg in cmdline:
                    if arg.endswith(ext):
                        return arg
            
            # Return executable path as fallback
            return exe_path
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    def _get_service_name(self, service_path):
        """Extract service name from path"""
        if service_path:
            return os.path.basename(service_path)
        return "Unknown"
    
    def _get_file_type(self, file_path):
        """Get file type based on extension"""
        if not file_path:
            return "Unknown"
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.jar':
            return 'JAR'
        elif ext == '.exe':
            return 'EXE'
        elif ext == '.bat':
            return 'BAT'
        elif ext == '.sh':
            return 'SH'
        return 'Unknown'
    
    def get_all_services(self):
        """Get all running services (JAR, EXE, BAT, SH) with their status and utilization"""
        services = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'status', 'create_time']):
                try:
                    if self._is_service_process(proc):
                        service_path = self._get_service_path(proc)
                        service_name = self._get_service_name(service_path)
                        file_type = self._get_file_type(service_path)
                        
                        # Get CPU and memory utilization
                        cpu_percent = proc.cpu_percent(interval=0.1)
                        memory_info = proc.memory_info()
                        memory_mb = memory_info.rss / (1024 * 1024)
                        
                        # Get process status
                        status = proc.status()
                        
                        # Calculate uptime
                        create_time = datetime.fromtimestamp(proc.create_time())
                        uptime = datetime.now() - create_time
                        
                        service_info = {
                            'pid': proc.pid,
                            'service_name': service_name,
                            'jar_name': service_name,  # Keep for backward compatibility
                            'service_path': service_path or 'Unknown',
                            'jar_path': service_path or 'Unknown',  # Keep for backward compatibility
                            'file_type': file_type,
                            'status': status,
                            'cpu_percent': round(cpu_percent, 2),
                            'memory_mb': round(memory_mb, 2),
                            'uptime_seconds': int(uptime.total_seconds()),
                            'uptime_formatted': str(uptime).split('.')[0],  # Remove microseconds
                            'start_time': create_time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                        
                        services.append(service_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            logger.error(f"Error scanning processes: {str(e)}")
            raise
        
        return services
    
    def get_service_details(self, pid):
        """Get detailed information about a specific service"""
        try:
            proc = psutil.Process(pid)
            
            if not self._is_service_process(proc):
                return None
            
            service_path = self._get_service_path(proc)
            service_name = self._get_service_name(service_path)
            file_type = self._get_file_type(service_path)
            
            # Get comprehensive process information
            cpu_percent = proc.cpu_percent(interval=0.1)
            memory_info = proc.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            # Get command line
            cmdline = ' '.join(proc.cmdline())
            
            # Get process status
            status = proc.status()
            
            # Calculate uptime
            create_time = datetime.fromtimestamp(proc.create_time())
            uptime = datetime.now() - create_time
            
            # Get number of threads
            num_threads = proc.num_threads()
            
            # Get open files/connections count
            try:
                num_fds = len(proc.open_files())
            except (psutil.AccessDenied, AttributeError):
                num_fds = 0
            
            # Get network connections
            try:
                connections = proc.connections()
                num_connections = len(connections)
            except (psutil.AccessDenied, AttributeError):
                num_connections = 0
            
            details = {
                'pid': pid,
                'service_name': service_name,
                'jar_name': service_name,  # Keep for backward compatibility
                'service_path': service_path or 'Unknown',
                'jar_path': service_path or 'Unknown',  # Keep for backward compatibility
                'file_type': file_type,
                'status': status,
                'cpu_percent': round(cpu_percent, 2),
                'memory_mb': round(memory_mb, 2),
                'memory_percent': round(proc.memory_percent(), 2),
                'uptime_seconds': int(uptime.total_seconds()),
                'uptime_formatted': str(uptime).split('.')[0],
                'start_time': create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'num_threads': num_threads,
                'num_open_files': num_fds,
                'num_connections': num_connections,
                'cmdline': cmdline,
                'username': proc.username() if hasattr(proc, 'username') else 'Unknown'
            }
            
            return details
        except psutil.NoSuchProcess:
            return None
        except Exception as e:
            logger.error(f"Error getting service details: {str(e)}")
            raise
    
    def stop_service(self, pid):
        """Stop a service (JAR, EXE, BAT, SH)"""
        try:
            proc = psutil.Process(pid)
            
            if not self._is_service_process(proc):
                return {
                    'success': False,
                    'error': 'Process is not a monitored service'
                }
            
            # Try graceful termination first
            try:
                proc.terminate()
                proc.wait(timeout=10)
                return {
                    'success': True,
                    'message': 'Service stopped gracefully'
                }
            except psutil.TimeoutExpired:
                # Force kill if graceful termination fails
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                    return {
                        'success': True,
                        'message': 'Service force stopped'
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'Failed to kill process: {str(e)}'
                    }
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Failed to stop process: {str(e)}'
                }
        except psutil.NoSuchProcess:
            return {
                'success': False,
                'error': 'Process not found'
            }
        except Exception as e:
            logger.error(f"Error stopping service: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def start_service(self, service_path, args=None):
        """Start a service (JAR, EXE, BAT, SH) as a detached process that survives parent termination"""
        try:
            if not os.path.exists(service_path):
                return {
                    'success': False,
                    'error': f'Service file not found: {service_path}'
                }
            
            # Determine file type and build appropriate command
            file_ext = os.path.splitext(service_path)[1].lower()
            cmd = []
            
            if file_ext == '.jar':
                # Java JAR file
                cmd = ['java']
                if args:
                    if isinstance(args, str):
                        cmd.extend(args.split())
                    elif isinstance(args, list):
                        cmd.extend(args)
                cmd.extend(['-jar', service_path])
            elif file_ext == '.exe':
                # Windows executable
                cmd = [service_path]
                if args:
                    if isinstance(args, str):
                        cmd.extend(args.split())
                    elif isinstance(args, list):
                        cmd.extend(args)
            elif file_ext == '.bat':
                # Windows batch file
                if self.system == 'Windows':
                    cmd = ['cmd', '/c', service_path]
                else:
                    return {
                        'success': False,
                        'error': 'BAT files are only supported on Windows'
                    }
                if args:
                    if isinstance(args, str):
                        cmd.extend(args.split())
                    elif isinstance(args, list):
                        cmd.extend(args)
            elif file_ext == '.sh':
                # Shell script (macOS/Linux)
                if self.system == 'Windows':
                    return {
                        'success': False,
                        'error': 'SH files are not supported on Windows'
                    }
                # Make sure script is executable
                if not os.access(service_path, os.X_OK):
                    os.chmod(service_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                cmd = ['/bin/bash', service_path] if self.system != 'Windows' else [service_path]
                if args:
                    if isinstance(args, str):
                        cmd.extend(args.split())
                    elif isinstance(args, list):
                        cmd.extend(args)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported file type: {file_ext}. Supported: .jar, .exe, .bat, .sh'
                }
            
            # Prepare process arguments for detached execution
            process_kwargs = {}
            
            if platform.system() == 'Windows':
                # Windows: Use DETACHED_PROCESS and CREATE_NEW_PROCESS_GROUP
                # This makes the process independent of the parent
                DETACHED_PROCESS = 0x00000008
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                process_kwargs['creationflags'] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                # Redirect output to null device to prevent hanging
                process_kwargs['stdout'] = subprocess.DEVNULL
                process_kwargs['stderr'] = subprocess.DEVNULL
                process_kwargs['stdin'] = subprocess.DEVNULL
            else:
                # macOS/Linux: Use setsid to create new session and detach from parent
                process_kwargs['stdout'] = subprocess.DEVNULL
                process_kwargs['stderr'] = subprocess.DEVNULL
                process_kwargs['stdin'] = subprocess.DEVNULL
                process_kwargs['start_new_session'] = True  # Creates new session (detached)
            
            # Start the detached process
            process = subprocess.Popen(cmd, **process_kwargs)
            
            # Wait a moment to check if it started successfully
            import time
            time.sleep(1)
            
            # Check if process is still running
            if process.poll() is None:
                # Process is running and detached
                logger.info(f"Started detached service: PID {process.pid}, File: {service_path}, Type: {file_ext}")
                return {
                    'success': True,
                    'pid': process.pid,
                    'message': f'Service started successfully as detached process ({file_ext})'
                }
            else:
                # Process exited immediately (error)
                error_msg = f'Service failed to start. '
                if file_ext == '.jar':
                    error_msg += 'Check Java installation and JAR file.'
                elif file_ext == '.exe':
                    error_msg += 'Check if executable is compatible with your system.'
                elif file_ext == '.bat':
                    error_msg += 'Check batch file syntax and dependencies.'
                elif file_ext == '.sh':
                    error_msg += 'Check script permissions and syntax.'
                else:
                    error_msg += 'Check file and system compatibility.'
                return {
                    'success': False,
                    'error': error_msg
                }
        except Exception as e:
            logger.error(f"Error starting service: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

