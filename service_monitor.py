"""
Service Monitor Module
Handles detection, monitoring, and control of Java JAR services on Windows, macOS, and Linux
"""

import psutil
import subprocess
import os
import platform
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ServiceMonitor:
    """Monitor and control Java JAR services"""
    
    def __init__(self):
        """Initialize the service monitor"""
        self.java_processes = []
    
    def _is_java_process(self, process):
        """Check if a process is a Java process"""
        try:
            cmdline = process.cmdline()
            if not cmdline:
                return False
            
            # Check if it's a java process
            if 'java' in cmdline[0].lower() or 'javaw' in cmdline[0].lower():
                # Check if it's running a JAR file
                for arg in cmdline:
                    if arg.endswith('.jar'):
                        return True
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
    
    def _get_jar_path(self, process):
        """Extract JAR file path from process command line"""
        try:
            cmdline = process.cmdline()
            for arg in cmdline:
                if arg.endswith('.jar'):
                    return arg
            return None
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    def _get_jar_name(self, jar_path):
        """Extract JAR name from path"""
        if jar_path:
            return os.path.basename(jar_path)
        return "Unknown"
    
    def get_all_services(self):
        """Get all running Java JAR services with their status and utilization"""
        services = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'status', 'create_time']):
                try:
                    if self._is_java_process(proc):
                        jar_path = self._get_jar_path(proc)
                        jar_name = self._get_jar_name(jar_path)
                        
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
                            'jar_name': jar_name,
                            'jar_path': jar_path or 'Unknown',
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
            
            if not self._is_java_process(proc):
                return None
            
            jar_path = self._get_jar_path(proc)
            jar_name = self._get_jar_name(jar_path)
            
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
                'jar_name': jar_name,
                'jar_path': jar_path or 'Unknown',
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
        """Stop a Java JAR service"""
        try:
            proc = psutil.Process(pid)
            
            if not self._is_java_process(proc):
                return {
                    'success': False,
                    'error': 'Process is not a Java JAR service'
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
    
    def start_service(self, jar_path, java_args=None):
        """Start a Java JAR service as a detached process that survives parent termination"""
        try:
            if not os.path.exists(jar_path):
                return {
                    'success': False,
                    'error': f'JAR file not found: {jar_path}'
                }
            
            # Build command
            cmd = ['java']
            
            # Add Java arguments if provided
            if java_args:
                if isinstance(java_args, str):
                    cmd.extend(java_args.split())
                elif isinstance(java_args, list):
                    cmd.extend(java_args)
            
            # Add JAR file
            cmd.extend(['-jar', jar_path])
            
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
                logger.info(f"Started detached Java service: PID {process.pid}, JAR: {jar_path}")
                return {
                    'success': True,
                    'pid': process.pid,
                    'message': 'Service started successfully as detached process'
                }
            else:
                # Process exited immediately (error)
                return {
                    'success': False,
                    'error': 'Service failed to start. Check Java installation and JAR file.'
                }
        except Exception as e:
            logger.error(f"Error starting service: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

