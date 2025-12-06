"""
MSMQ (Microsoft Message Queuing) Monitor Module
Monitors Windows Message Queues and provides message count information
Windows-specific module
"""

import subprocess
import platform
import logging
import re
import json
import os

logger = logging.getLogger(__name__)


class MSMQMonitor:
    """Monitor Windows Message Queues"""
    
    def __init__(self):
        """Initialize the MSMQ monitor"""
        self.system = platform.system()
        self.is_windows = self.system == 'Windows'
        
        if not self.is_windows:
            logger.warning("MSMQ monitoring is only available on Windows")
    
    def _execute_powershell(self, command):
        """Execute a PowerShell command and return the result"""
        if not self.is_windows:
            return None
        
        try:
            # Use PowerShell to execute the command
            ps_command = f'powershell.exe -Command "{command}"'
            result = subprocess.run(
                ps_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"PowerShell command failed: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error("PowerShell command timed out")
            return None
        except Exception as e:
            logger.error(f"Error executing PowerShell command: {str(e)}")
            return None
    
    def get_all_queues(self):
        """
        Get all MSMQ queues with their message counts
        Returns a list of dictionaries with queue information
        """
        if not self.is_windows:
            return []
        
        queues = []
        
        try:
            # Get all queues using PowerShell Get-MsmqQueue cmdlet
            # This requires MSMQ PowerShell module to be installed
            ps_command = """
            $queues = Get-MsmqQueue -QueueType Private, Public -ErrorAction SilentlyContinue
            $result = @()
            foreach ($queue in $queues) {
                $queueInfo = @{
                    Name = $queue.Name
                    MessageCount = $queue.MessageCount
                    QueueType = $queue.QueueType
                    Path = $queue.Path
                }
                $result += $queueInfo
            }
            $result | ConvertTo-Json -Compress
            """
            
            output = self._execute_powershell(ps_command)
            
            if output:
                try:
                    queues_data = json.loads(output)
                    if isinstance(queues_data, list):
                        queues = queues_data
                    elif isinstance(queues_data, dict):
                        queues = [queues_data]
                except json.JSONDecodeError:
                    logger.warning("Failed to parse PowerShell JSON output")
                    # Fallback: try parsing manually
                    queues = self._parse_queue_output_manual(output)
        except Exception as e:
            logger.error(f"Error getting MSMQ queues: {str(e)}")
            # Try alternative method using WMI
            queues = self._get_queues_wmi()
        
        return queues
    
    def _get_queues_wmi(self):
        """Alternative method: Get queues using WMI"""
        queues = []
        
        try:
            # Use WMI to get queue information
            ps_command = """
            $queues = Get-WmiObject -Class Win32_PerfRawData_MSMQ_MSMQQueue -ErrorAction SilentlyContinue
            $result = @()
            foreach ($queue in $queues) {
                $queueName = $queue.Name
                $messageCount = $queue.MessagesInQueue
                if ($queueName -and $messageCount -ge 0) {
                    $queueInfo = @{
                        Name = $queueName
                        MessageCount = $messageCount
                        QueueType = "Unknown"
                        Path = ""
                    }
                    $result += $queueInfo
                }
            }
            $result | ConvertTo-Json -Compress
            """
            
            output = self._execute_powershell(ps_command)
            
            if output:
                try:
                    queues_data = json.loads(output)
                    if isinstance(queues_data, list):
                        queues = queues_data
                    elif isinstance(queues_data, dict):
                        queues = [queues_data]
                except json.JSONDecodeError:
                    logger.warning("Failed to parse WMI JSON output")
        except Exception as e:
            logger.error(f"Error getting queues via WMI: {str(e)}")
        
        return queues
    
    def _parse_queue_output_manual(self, output):
        """Manual parsing fallback if JSON parsing fails"""
        queues = []
        # This is a fallback - would need to parse text output
        # For now, return empty list
        return queues
    
    def get_queue_by_name(self, queue_name):
        """
        Get a specific queue by name
        Returns queue info dict or None
        """
        all_queues = self.get_all_queues()
        
        for queue in all_queues:
            # Queue name might be in format: "computername\\private$\\queuename"
            # or just "queuename"
            queue_display_name = queue.get('Name', '')
            
            # Extract just the queue name (last part after \\)
            if '\\' in queue_display_name:
                queue_name_parts = queue_display_name.split('\\')
                queue_simple_name = queue_name_parts[-1]
            else:
                queue_simple_name = queue_display_name
            
            # Compare (case-insensitive, without extension)
            if queue_simple_name.lower() == queue_name.lower():
                return queue
        
        return None
    
    def extract_queue_simple_name(self, queue_name):
        """
        Extract simple queue name from MSMQ queue name format
        Handles formats like:
        - computername\private$\queuename
        - private$\queuename
        - queuename
        
        Returns:
            Simple queue name (without path prefixes)
        """
        if not queue_name:
            return ''
        
        # Remove common prefixes
        queue_name = queue_name.replace('private$\\', '').replace('public$\\', '')
        queue_name = queue_name.replace(r'private$/', '').replace(r'public$/', '')
        
        # Extract last part after backslash (for private queues: computername\private$\queuename)
        if '\\' in queue_name:
            parts = queue_name.split('\\')
            # Find the actual queue name (usually the last non-empty part)
            for part in reversed(parts):
                if part and part.lower() not in ['private$', 'public$']:
                    return part
            # Fallback: use last part
            queue_name = parts[-1]
        elif '/' in queue_name:
            parts = queue_name.split('/')
            for part in reversed(parts):
                if part and part.lower() not in ['private$', 'public$']:
                    return part
            queue_name = parts[-1]
        
        # Remove any remaining $ signs
        queue_name = queue_name.replace('$', '')
        
        return queue_name.strip()
    
    def match_queue_to_executable(self, queue_name, executable_files):
        """
        Match a queue name to an executable file
        Queue names typically match executable names (without extension)
        
        Args:
            queue_name: Name of the MSMQ queue
            executable_files: List of executable file paths or names
        
        Returns:
            Matched executable file path or None
        """
        # Extract simple queue name
        queue_simple_name = self.extract_queue_simple_name(queue_name)
        
        if not queue_simple_name:
            return None
        
        # Remove extension if present
        queue_simple_name = os.path.splitext(queue_simple_name)[0]
        
        for exe_file in executable_files:
            # Get just the filename without path
            if os.path.sep in exe_file:
                exe_filename = os.path.basename(exe_file)
            else:
                exe_filename = exe_file
            
            # Get filename without extension
            exe_name_without_ext = os.path.splitext(exe_filename)[0]
            
            # Compare (case-insensitive)
            if exe_name_without_ext.lower() == queue_simple_name.lower():
                logger.debug(f"Matched queue '{queue_name}' (simple: '{queue_simple_name}') to executable '{exe_file}'")
                return exe_file
        
        return None
    
    def get_queue_message_count(self, queue_name):
        """
        Get message count for a specific queue
        Returns message count (int) or None if queue not found
        """
        queue = self.get_queue_by_name(queue_name)
        if queue:
            return queue.get('MessageCount', 0)
        return None
    
    def is_msmq_available(self):
        """Check if MSMQ is available on this system"""
        if not self.is_windows:
            return False
        
        try:
            # Try to execute a simple PowerShell command to check MSMQ
            ps_command = "Get-Command Get-MsmqQueue -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"
            result = self._execute_powershell(ps_command)
            return result is not None and 'Get-MsmqQueue' in result
        except Exception:
            return False

