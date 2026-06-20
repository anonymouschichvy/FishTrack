#!/usr/bin/env python3
"""
BASE Station Utility Functions
Helper functions for message handling and data processing
FIXED: Enhanced error handling and logging for data saving
"""

import uuid
import time
import hashlib
import zlib
import base64
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger("LoRaController")


def generate_msg_id() -> str:
    """Generate unique message ID"""
    return str(uuid.uuid4())[:8]


def calculate_checksum(data: bytes) -> str:
    """Calculate SHA256 checksum of data"""
    return hashlib.sha256(data).hexdigest()


def compress_data(data: Dict[str, Any]) -> bytes:
    """Compress JSON data"""
    json_str = json.dumps(data, separators=(',', ':'))
    return zlib.compress(json_str.encode(), level=9)


def decompress_data(compressed: bytes) -> Dict[str, Any]:
    """Decompress data back to JSON"""
    decompressed = zlib.decompress(compressed)
    return json.loads(decompressed.decode())


def format_timestamp(timestamp: Optional[float] = None) -> str:
    """Format Unix timestamp to readable string"""
    if timestamp is None:
        timestamp = time.time()
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def get_node_status(node_info: Dict[str, Any], current_time: float) -> str:
    """Determine node status based on last seen time"""
    last_seen = node_info.get("last_seen", 0)
    time_diff = current_time - last_seen
    
    if time_diff < 60:
        return "ONLINE"
    elif time_diff < 180:
        return "IDLE"
    elif time_diff < 300:
        return "WARNING"
    else:
        return "OFFLINE"


def calculate_signal_strength(rssi: Optional[int]) -> str:
    """Convert RSSI to signal strength description"""
    if rssi is None:
        return "Unknown"
    elif rssi > -60:
        return "Excellent"
    elif rssi > -70:
        return "Good"
    elif rssi > -80:
        return "Fair"
    elif rssi > -90:
        return "Weak"
    else:
        return "Poor"


def create_command_packet(target: str, scripts: List[str], 
                         args_dict: Dict[str, List[str]]) -> Dict[str, Any]:
    """Create a command packet for sending to BUOY node"""
    from config import MSG_TYPE_COMMAND, DEFAULT_TTL, CODENAME
    
    return {
        "msg_id": generate_msg_id(),
        "type": MSG_TYPE_COMMAND,
        "from": CODENAME,
        "to": target,
        "target": target,
        "scripts": scripts,
        "args": args_dict,
        "ttl": DEFAULT_TTL,
        "via": [],
        "timestamp": time.time()
    }


def save_json_data(data: Dict[str, Any], filepath, add_timestamp: bool = True) -> bool:
    """
    Save JSON data to file with comprehensive error handling
    CRITICAL FIX: Proper error logging and directory creation
    """
    try:
        # CRITICAL FIX #1: Convert filepath to Path object if it's a string
        if isinstance(filepath, str):
            filepath = Path(filepath)
        
        # CRITICAL FIX #2: Ensure parent directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # CRITICAL FIX #3: Add timestamp if requested
        if add_timestamp and isinstance(data, dict):
            data["saved_at_base"] = datetime.utcnow().isoformat()
        
        # CRITICAL FIX #4: Handle non-serializable data
        # Create a copy to avoid modifying original
        data_to_save = data.copy() if isinstance(data, dict) else data
        
        # CRITICAL FIX #5: Write to temp file first (atomic write)
        temp_filepath = filepath.with_suffix('.tmp')
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False, default=str)
        
        # CRITICAL FIX #6: Verify the file was written correctly
        with open(temp_filepath, 'r', encoding='utf-8') as f:
            json.load(f)  # Will raise exception if invalid JSON
        
        # CRITICAL FIX #7: Atomic rename
        temp_filepath.replace(filepath)
        
        logger.debug(f"[SAVE] ✅ Saved data to {filepath.name} ({filepath.stat().st_size} bytes)")
        return True
        
    except json.JSONDecodeError as e:
        logger.error(f"[SAVE] ❌ JSON encoding error for {filepath}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Clean up temp file
        if temp_filepath and temp_filepath.exists():
            temp_filepath.unlink()
        return False
        
    except PermissionError as e:
        logger.error(f"[SAVE] ❌ Permission denied writing to {filepath}: {e}")
        return False
        
    except OSError as e:
        logger.error(f"[SAVE] ❌ OS error writing to {filepath}: {e}")
        return False
        
    except Exception as e:
        logger.error(f"[SAVE] ❌ Unexpected error saving to {filepath}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def load_json_data(filepath):
    """
    Load JSON data from file with error handling
    CRITICAL FIX: Better error logging
    """
    try:
        # Convert to Path object if string
        if isinstance(filepath, str):
            filepath = Path(filepath)
        
        if not filepath.exists():
            logger.debug(f"[LOAD] File not found: {filepath}")
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.debug(f"[LOAD] ✅ Loaded data from {filepath.name}")
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"[LOAD] ❌ Invalid JSON in {filepath}: {e}")
        return None
        
    except PermissionError as e:
        logger.error(f"[LOAD] ❌ Permission denied reading {filepath}: {e}")
        return None
        
    except Exception as e:
        logger.error(f"[LOAD] ❌ Error loading {filepath}: {e}")
        return None


def validate_data_directory(directory: Path) -> bool:
    """
    Validate that a data directory exists and is writable
    CRITICAL FIX: Helps diagnose data saving issues
    """
    try:
        # Create directory if it doesn't exist
        directory.mkdir(parents=True, exist_ok=True)
        
        # Test write permissions
        test_file = directory / ".write_test"
        with open(test_file, 'w') as f:
            f.write("test")
        test_file.unlink()
        
        logger.debug(f"[VALIDATE] ✅ Directory validated: {directory}")
        return True
        
    except Exception as e:
        logger.error(f"[VALIDATE] ❌ Directory validation failed for {directory}: {e}")
        return False


def log_data_save_attempt(data: Dict[str, Any], sender: str, data_type: str, filepath: Path):
    """
    Log detailed information about data save attempt
    CRITICAL FIX: Helps diagnose what's not being saved
    """
    try:
        data_size = len(json.dumps(data))
        logger.info(f"[SAVE] Attempting to save {data_type} data from {sender}")
        logger.info(f"[SAVE]   → File: {filepath.name}")
        logger.info(f"[SAVE]   → Size: {data_size} bytes")
        logger.info(f"[SAVE]   → Keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
    except Exception as e:
        logger.error(f"[SAVE] Error logging save attempt: {e}")