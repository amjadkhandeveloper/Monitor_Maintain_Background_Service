"""
Constants and Default Configuration Values
Centralized location for all default values and configuration constants
"""

# Server Configuration
DEFAULT_PORT = 5001  # Default Flask port (changed from 5000 to avoid macOS AirPlay Receiver conflict)
DEFAULT_HOST = '0.0.0.0'  # Listen on all interfaces

# Auto-Restart Thresholds (Defaults)
# ======================================
# CHANGE THESE VALUES TO CUSTOMIZE AUTO-RESTART BEHAVIOR
# After modifying, restart the application for changes to take effect
# ======================================

DEFAULT_CPU_THRESHOLD = 80.0  # Default CPU threshold percentage
DEFAULT_MEMORY_THRESHOLD_MB = 1000.0  # Default memory threshold in MB (1 GB)

# MSMQ Queue Threshold (Windows Only)
# This is the default number of messages in MSMQ queue that triggers auto-restart
# Example: If set to 25000, services will auto-restart when queue has >= 25000 messages
# You can change this value and restart the program to use the new threshold
DEFAULT_QUEUE_THRESHOLD = 1000  # Default MSMQ queue message threshold

# Threshold Limits (Validation)
CPU_THRESHOLD_MIN = 1  # Minimum CPU threshold percentage
CPU_THRESHOLD_MAX = 100  # Maximum CPU threshold percentage

MEMORY_THRESHOLD_MIN_MB = 1  # Minimum memory threshold in MB
MEMORY_THRESHOLD_MAX_MB = 10240  # Maximum memory threshold in MB (10 GB)

QUEUE_THRESHOLD_MIN = 1  # Minimum queue threshold (messages)
QUEUE_THRESHOLD_MAX = 1000000  # Maximum queue threshold (messages)

# Auto-Restart Monitoring Intervals
AUTO_RESTART_CHECK_INTERVAL = 30  # Check every 30 seconds
AUTO_RESTART_ERROR_RETRY_INTERVAL = 60  # Wait 60 seconds on error before retry

# Restart Delays (in seconds)
RESTART_DELAY_CPU_MEMORY = 120  # 2 minutes delay for CPU/Memory-based restarts
RESTART_DELAY_QUEUE = 60  # 1 minute delay for queue-based restarts

# Dashboard UI Configuration
DASHBOARD_REFRESH_INTERVAL_MS = 20000  # 20 seconds (in milliseconds)
MESSAGE_DISPLAY_DURATION_MS = 5000  # 5 seconds

# Supported File Extensions by OS
SUPPORTED_EXTENSIONS = {
    'Windows': ['.jar', '.exe', '.bat'],
    'Darwin': ['.jar', '.sh'],  # macOS
    'Linux': ['.jar', '.sh']
}

# File Type Labels
FILE_TYPE_LABELS = {
    'JAR': 'JAR',
    'EXE': 'EXE',
    'BAT': 'BAT',
    'SH': 'SH'
}

# Memory Display Scale (for visualization)
MEMORY_DISPLAY_SCALE_MB = 2000  # Used for memory bar visualization (2000 MB = 100%)

# Process Status Colors (for UI)
STATUS_COLORS = {
    'running': 'status-running',
    'stopped': 'status-stopped',
    'zombie': 'status-zombie'
}

# Utilization Bar Thresholds (for color coding)
CPU_HIGH_THRESHOLD = 80  # CPU percentage considered "high"
MEMORY_HIGH_THRESHOLD_MB = 1000  # Memory MB considered "high"
QUEUE_WARNING_THRESHOLD_PERCENT = 0.8  # 80% of threshold triggers warning color

