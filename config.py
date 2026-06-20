#!/usr/bin/env python3
"""
BASE Station Configuration - LoRa Mesh Network
All configuration constants and settings
"""

import os
from pathlib import Path

# ===== HARDWARE CONFIGURATION =====
SERIAL_PORT = "COM4"
BAUD_RATE = 115200
MAX_PACKET_SIZE = 200

# ===== NODE CONFIGURATION =====
CODENAME = "ATLAS - BASE_STATION"
DEFAULT_TTL = 5

# ===== ACTIVE LIST - Expected BUOY Nodes =====
ACTIVE_BUOY_LIST = [
    "BUOY-POSEIDON",
]

# ===== TIMING CONFIGURATION =====
NEIGHBOR_TIMEOUT = 300  # seconds
CHUNK_TIMEOUT = 120  # seconds
DISCOVERY_INTERVAL = 60  # seconds
CLEANUP_INTERVAL = 120  # seconds
RETRY_CHECK_INTERVAL = 10  # seconds
TABLE_PRINT_INTERVAL = 30  # seconds
STATS_PRINT_INTERVAL = 60  # seconds
BATTERY_MONITOR_INTERVAL = 600  # 10 minutes

# ===== ACK & RETRY CONFIGURATION =====
ACK_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
CHUNK_ACK_TIMEOUT = 10  # seconds
MAX_CHUNK_RETRIES = 3
CHUNK_RETRY_DELAY = 2  # base delay between retries

# ===== BUFFER & QUEUE LIMITS =====
RX_BUFFER_MAX = 2048
MAX_SEEN_MESSAGES = 1000
MAX_SEND_QUEUE_SIZE = 50
MAX_OUTPUT_QUEUE_SIZE = 1000

# ===== COMPRESSION SETTINGS =====
COMPRESSION_LEVEL = 9  # 1-9, higher = better compression

# ===== MESSAGE TYPES =====
MSG_TYPE_PING = "ping"
MSG_TYPE_ACK = "ack"
MSG_TYPE_COMMAND = "command"
MSG_TYPE_LINUX_CMD = "linux_cmd"  # Added Linux command type
MSG_TYPE_CMD_ACK = "cmd_ack"
MSG_TYPE_CMD_STATUS = "cmd_status"
MSG_TYPE_DATA = "data"
MSG_TYPE_CHUNK = "chunk"
MSG_TYPE_CHUNK_ACK = "chunk_ack"
MSG_TYPE_ALERT = "alert"
MSG_TYPE_ALIVE = "alive"
MSG_TYPE_BATTERY = "battery"
MSG_TYPE_GPS = "gps"

# ===== FILE PATHS =====
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Create directories
for dir_path in [DATA_DIR, LOGS_DIR]:
    dir_path.mkdir(exist_ok=True)

# Data storage paths
RECEIVED_DATA_DIR = DATA_DIR / "received"
FISH_DATA_DIR = RECEIVED_DATA_DIR / "fish_detection"
SONAR_DATA_DIR = RECEIVED_DATA_DIR / "sonar_detection"
GPS_DATA_DIR = RECEIVED_DATA_DIR / "gps_data"
BATTERY_DATA_DIR = RECEIVED_DATA_DIR / "battery_data"
COMMAND_RESULTS_DIR = RECEIVED_DATA_DIR / "command_results"

# Analytics paths
ANALYTICS_DIR = DATA_DIR / "analytics"
PREDICTIONS_DIR = ANALYTICS_DIR / "predictions"
DAILY_SUMMARIES_DIR = ANALYTICS_DIR / "daily_summaries"
TIMELINE_SUMMARIES_DIR = ANALYTICS_DIR / "timeline_summaries"

# Create subdirectories
for dir_path in [FISH_DATA_DIR, SONAR_DATA_DIR, GPS_DATA_DIR, 
                 BATTERY_DATA_DIR, COMMAND_RESULTS_DIR, ANALYTICS_DIR, 
                 PREDICTIONS_DIR, DAILY_SUMMARIES_DIR, TIMELINE_SUMMARIES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ===== LOGGING CONFIGURATION =====
LOG_FILE = LOGS_DIR / f"{CODENAME}.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# ===== WEB SERVER CONFIGURATION =====
WEB_HOST = "0.0.0.0"
WEB_PORT = 8080
WEB_DEBUG = False

# ===== COMMAND REGISTRY =====
AVAILABLE_COMMANDS = {
    "fish_detect": {
        "label": "Fish Detection",
        "description": "Run fish detection with camera",
        "available_args": [
            {"name": "--time", "type": "str", "help": "Duration (e.g., 15min, 2h, 30s)"},
            {"name": "--interval", "type": "str", "help": "Interval between cycles"},
            {"name": "--preview", "choices": ["on", "off"], "default": "on"},
            {"name": "--no-kill-switch", "type": "flag", "help": "Disable kill switch"}
        ]
    },
    "sonar": {
        "label": "Sonar Detection",
        "description": "Run sonar data capture",
        "available_args": [
            {"name": "--preview", "choices": ["on", "off"], "default": "on"},
            {"name": "--simulate", "type": "flag", "help": "Enable simulation mode"},
            {"name": "--detect", "type": "flag", "help": "Enable fish detection"},
            {"name": "--time", "type": "str", "help": "Duration (e.g., 15min, 2h, 30s)"}
        ]
    },
    "gps": {
        "label": "GPS Reading",
        "description": "Capture GPS coordinates",
        "available_args": []
    },
    "battery": {
        "label": "Battery Status",
        "description": "Get battery status report",
        "available_args": []
    }
}

# ===== SCHEDULER CONFIGURATION =====
SCHEDULER_ENABLED = True
SCHEDULED_COMMANDS_FILE = DATA_DIR / "scheduled_commands.json"

# ===== STATISTICS TRACKING =====
STATS_KEYS = [
    "packets_sent",
    "packets_received",
    "packets_forwarded",
    "chunks_reassembled",
    "duplicates_dropped",
    "send_failures",
    "reconnections",
    "chunk_acks_received",
    "chunk_retries",
    "commands_sent",
    "commands_completed"
]