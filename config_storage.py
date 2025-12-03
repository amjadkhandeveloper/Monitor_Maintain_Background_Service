"""
Configuration Storage Module
Handles persistent storage of auto-restart configurations and folder paths
"""

import json
import os
import logging
from threading import Lock

logger = logging.getLogger(__name__)

CONFIG_FILE = 'monitor_config.json'
config_lock = Lock()


def load_config():
    """Load configuration from file"""
    if not os.path.exists(CONFIG_FILE):
        return {
            'auto_restart': {},  # Keyed by service_name instead of PID
            'folder_path': None
        }
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Ensure structure exists
            if 'auto_restart' not in config:
                config['auto_restart'] = {}
            if 'folder_path' not in config:
                config['folder_path'] = None
            return config
    except Exception as e:
        logger.error(f"Error loading config file: {str(e)}")
        return {
            'auto_restart': {},
            'folder_path': None
        }


def save_config(config):
    """Save configuration to file"""
    try:
        with config_lock:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Configuration saved to {CONFIG_FILE}")
            return True
    except Exception as e:
        logger.error(f"Error saving config file: {str(e)}")
        return False


def get_auto_restart_config_by_name(service_name):
    """Get auto-restart config by service name"""
    config = load_config()
    return config.get('auto_restart', {}).get(service_name, None)


def save_auto_restart_config(service_name, config_data):
    """Save auto-restart config for a service by name"""
    config = load_config()
    if not config.get('auto_restart'):
        config['auto_restart'] = {}
    
    config['auto_restart'][service_name] = config_data
    return save_config(config)


def delete_auto_restart_config(service_name):
    """Delete auto-restart config for a service"""
    config = load_config()
    if service_name in config.get('auto_restart', {}):
        del config['auto_restart'][service_name]
        return save_config(config)
    return True


def get_folder_path():
    """Get stored folder path"""
    config = load_config()
    return config.get('folder_path')


def save_folder_path(folder_path):
    """Save folder path"""
    config = load_config()
    config['folder_path'] = folder_path
    return save_config(config)

