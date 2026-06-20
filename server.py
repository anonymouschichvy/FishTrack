#!/usr/bin/env python3
"""
BASE Station Web Server - Flask API & Dashboard
Production version - Works with existing config.py
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
import json
import logging
import time
from datetime import datetime
from pathlib import Path
import hashlib
import uuid
import sys

# Setup basic logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# ===== CONFIGURATION =====
# Import from config.py in same directory
from config import *

# Import analytics and prediction components
try:
    from analytics import ANALYTICS_AVAILABLE, daily_aggregator, prediction_service, run_daily_aggregation
except ImportError as e:
    logging.warning(f"Could not import analytics: {e}")
    ANALYTICS_AVAILABLE = False
    daily_aggregator = None
    prediction_service = None

# Map config variables to expected names
SERVER_HOST = WEB_HOST
SERVER_PORT = WEB_PORT

logging.info("✓ Loaded configuration from config.py")
logging.info(f"  Data directory: {RECEIVED_DATA_DIR}")
logging.info(f"  Fish data: {FISH_DATA_DIR}")
logging.info(f"  Sonar data: {SONAR_DATA_DIR}")
logging.info(f"  GPS data: {GPS_DATA_DIR}")


# ===== UTILITY FUNCTIONS =====

def log_audit_event(action, details, operator="Operator", node="N/A", status="info"):
    try:
        audit_file = DATA_DIR / "audit_log.json"
        existing = []
        if audit_file.exists():
            existing_data = load_json_data(audit_file)
            if isinstance(existing_data, list):
                existing = existing_data
        
        existing.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "operator": operator,
            "details": details,
            "status": status,
            "node": node
        })
        save_json_data(existing, audit_file, add_timestamp=False)
    except Exception as e:
        logging.error(f"Failed to log audit event: {e}")

def get_latest_files(directory: Path, limit=10):
    """Get latest JSON files from directory, sorted by modification time"""
    try:
        if not directory.exists():
            logging.debug(f"Directory not found: {directory}")
            return []
        
        json_files = list(directory.glob("*.json"))
        # Sort by modification time, newest first
        json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return json_files[:limit]
    except Exception as e:
        logging.error(f"Error getting files from {directory}: {e}")
        return []


def save_json_data(data, filepath: Path, add_timestamp=True):
    """Save data to JSON file"""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        if add_timestamp and isinstance(data, dict):
            data["_saved_at"] = datetime.utcnow().isoformat()
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        logging.error(f"Error saving to {filepath}: {e}")
        return False


def parse_battery_data(battery_dict):
    """Parse and format battery data for display"""
    try:
        cells = battery_dict.get("cells") or battery_dict.get("cells_mv", {})
        
        return {
            "timestamp": battery_dict.get("timestamp"),
            "charge_state": battery_dict.get("charge_state", "unknown"),
            "voltage_v": battery_dict.get("voltage_v") or (
                battery_dict.get("battery", {}).get("voltage_mv", 0) / 1000
            ),
            "current_ma": battery_dict.get("current_ma") or (
                battery_dict.get("battery", {}).get("current_ma", 0)
            ),
            "percent": battery_dict.get("percent") or (
                battery_dict.get("battery", {}).get("percent", 0)
            ),
            "remaining_mah": battery_dict.get("remaining_mah") or (
                battery_dict.get("battery", {}).get("remaining_mah", 0)
            ),
            "time_to_empty_min": battery_dict.get("time_to_empty_min") or (
                battery_dict.get("battery", {}).get("time_to_empty_min")
            ),
            "time_to_full_min": battery_dict.get("time_to_full_min") or (
                battery_dict.get("battery", {}).get("time_to_full_min")
            ),
            "low_voltage": battery_dict.get("low_voltage", False),
            "vbus_voltage_v": battery_dict.get("vbus_voltage_v") or (
                battery_dict.get("vbus", {}).get("voltage_mv", 0) / 1000
            ),
            "cells": cells
        }
    except Exception as e:
        return {"error": str(e), "timestamp": battery_dict.get("timestamp")}


def load_json_data(filepath: Path):
    """
    Safely load JSON data.
    Supports dict or list JSON roots.
    """
    try:
        if not filepath.exists():
            logging.debug(f"JSON file not found: {filepath}")
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, (dict, list)):
            logging.error(f"Invalid JSON root type in {filepath}: {type(data)}")
            return None

        return data

    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON format in {filepath}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error loading {filepath}: {e}")
        return None


def load_latest_data(directory: Path, limit=10):
    """Load latest JSON files from directory"""
    files = get_latest_files(directory, limit=limit)
    results = []

    for filepath in files:
        data = load_json_data(filepath)
        if data is None:
            continue

        # Normalize structure
        if isinstance(data, list):
            results.append({
                "records": data,
                "_filename": filepath.name,
                "_filepath": str(filepath)
            })
        elif isinstance(data, dict):
            data["_filename"] = filepath.name
            data["_filepath"] = str(filepath)
            results.append(data)

    return results


def load_data_with_fallback(reference_paths, data_dir, merge_multiple=False):
    """
    Smart data loading with fallback strategy:
    1. Try reference files (for demo/testing)
    2. Try actual data directory (for real collected data)
    3. Return None if nothing found
    """
    # Try reference files first
    for ref_path in reference_paths:
        try:
            if ref_path.exists():
                data = load_json_data(ref_path)
                if data:
                    logging.info(f"📁 Loaded reference data from: {ref_path}")
                    return data, "reference"
        except Exception as e:
            logging.debug(f"Error checking {ref_path}: {e}")
            continue
    
    # Try actual data directory
    try:
        if data_dir.exists():
            files = get_latest_files(data_dir, limit=50)
            if files:
                if merge_multiple:
                    # Load and merge multiple files
                    all_data = []
                    for f in files:
                        data = load_json_data(f)
                        if data:
                            if isinstance(data, list):
                                all_data.extend(data)
                            elif isinstance(data, dict):
                                all_data.append(data)
                    if all_data:
                        logging.info(f"📁 Loaded {len(all_data)} records from directory: {data_dir}")
                        return all_data, "directory"
                else:
                    # Return just the latest file
                    data = load_json_data(files[0])
                    if data:
                        logging.info(f"📁 Loaded latest file from: {files[0]}")
                        return data, "directory"
    except Exception as e:
        logging.debug(f"Error checking directory {data_dir}: {e}")
    
    logging.warning(f"⚠ No data found in reference paths or directory: {data_dir}")
    return None, None


def update_config_file(active_list):
    """Update the config.py file with new active list"""
    try:
        config_file = Path(__file__).parent / "config.py"
        
        if not config_file.exists():
            logging.warning("config.py not found, cannot update")
            return False
        
        with open(config_file, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        in_active_list = False
        
        for i, line in enumerate(lines):
            if line.strip().startswith('ACTIVE_BUOY_LIST'):
                new_lines.append('ACTIVE_BUOY_LIST = [\n')
                for node in active_list:
                    new_lines.append(f'    "{node}",\n')
                new_lines.append(']\n')
                in_active_list = True
            elif in_active_list and line.strip() == ']':
                in_active_list = False
            elif not in_active_list:
                new_lines.append(line)
        
        with open(config_file, 'w') as f:
            f.writelines(new_lines)
        
        return True
    except Exception as e:
        logging.error(f"Failed to update config.py: {e}")
        return False


# ===== FLASK APP SETUP =====

# Suppress Flask logging except errors
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__, 
            template_folder='web/templates',
            static_folder='web/static')
app.config['JSON_SORT_KEYS'] = False

# Global state reference
from logic import NetworkState
from hardware import LoRaController

network_state = NetworkState()
network_state.init_caches_from_disk()

lora_controller = LoRaController(SERIAL_PORT)
# Attempt to connect to hardware
# lora_controller.connect()

scheduler = None


# ===== SYSTEM API ENDPOINTS =====

@app.route('/api/status')
def api_status():
    """Get overall system status"""
    try:
        if not network_state:
            return jsonify({"error": "System not initialized"}), 500
        
        return jsonify({
            "codename": CODENAME,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": time.time(),
            "stats": network_state.stats,
            "connection_healthy": lora_controller.is_connected() if lora_controller else False
        })
    except Exception as e:
        logging.error(f"Error in api_status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/neighbors')
def api_neighbors():
    """Get neighbor table"""
    try:
        if not network_state:
            return jsonify({"error": "System not initialized"}), 500
        
        summary = network_state.get_neighbor_summary()
        
        neighbors_list = []
        current_time = time.time()
        
        for codename, info in summary.get("neighbors", {}).items():
            neighbors_list.append({
                "codename": codename,
                "last_seen": info.get("last_seen"),
                "last_direct": info.get("last_direct"),
                "hops": info.get("hops", "N/A"),
                "rssi": info.get("rssi"),
                "status": info.get("status", "UNKNOWN")
            })
        
        return jsonify({
            "total_neighbors": summary.get("total", 0),
            "direct": summary.get("direct", 0),
            "relay": summary.get("relay", 0),
            "neighbors": neighbors_list
        })
    except Exception as e:
        logging.error(f"Error in api_neighbors: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/active_list')
def api_active_list():
    """Get active list with status"""
    try:
        if not network_state:
            return jsonify({"error": "System not initialized"}), 500
        
        active_list_status = network_state.get_active_list_status()
        
        return jsonify({
            "nodes": active_list_status
        })
    except Exception as e:
        logging.error(f"Error in api_active_list: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/commands', methods=['GET', 'POST'])
def api_commands():
    """Get command status or send new command"""
    try:
        if not network_state:
            return jsonify({"error": "System not initialized"}), 500
        
        if request.method == 'GET':
            return jsonify({
                "active_commands": network_state.get_all_commands(),
                "linux_commands": network_state.get_all_linux_commands(),
                "available_commands": AVAILABLE_COMMANDS
            })
        
        elif request.method == 'POST':
            data = request.json
            target = data.get('target')
            scripts = data.get('scripts', [])
            args_dict = data.get('args', {})
            
            if not target or not scripts:
                return jsonify({"error": "Missing target or scripts"}), 400
            
            from logic import send_command_to_buoy

            command_id = send_command_to_buoy(
                network_state,
                lora_controller,
                target,
                scripts,
                args_dict
            )
            
            if command_id:
                log_audit_event(
                    action="SEND_SCRIPT",
                    details=f"Sent script(s) {', '.join(scripts)} with args {args_dict}",
                    operator=data.get("operator", "Operator"),
                    node=target,
                    status="success"
                )
                return jsonify({
                    "success": True,
                    "command_id": command_id,
                    "target": target,
                    "scripts": scripts
                })
            else:
                log_audit_event(
                    action="SEND_SCRIPT_FAIL",
                    details=f"Failed to send script(s) {', '.join(scripts)}",
                    operator=data.get("operator", "Operator"),
                    node=target,
                    status="error"
                )
                return jsonify({
                    "success": False,
                    "error": "Failed to send command"
                }), 500
    except Exception as e:
        logging.error(f"Error in api_commands: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/linux_commands', methods=['GET', 'POST'])
def api_linux_commands():
    """Get Linux command status or send new Linux command"""
    try:
        if not network_state:
            return jsonify({"error": "System not initialized"}), 500
        
        if request.method == 'GET':
            return jsonify({
                "active_linux_commands": network_state.get_all_linux_commands()
            })
        
        elif request.method == 'POST':
            data = request.json
            target = data.get('target')
            command = data.get('command', '').strip()
            
            if not target or not command:
                return jsonify({"error": "Missing target or command"}), 400
            
            from logic import send_linux_command_to_buoy

            command_id = send_linux_command_to_buoy(
                network_state,
                lora_controller,
                target,
                command
            )
            
            if command_id:
                log_audit_event(
                    action="SEND_LINUX",
                    details=f"Sent Linux command: {command}",
                    operator=data.get("operator", "Operator"),
                    node=target,
                    status="warning"
                )
                return jsonify({
                    "success": True,
                    "command_id": command_id,
                    "target": target,
                    "command": command
                })
            else:
                log_audit_event(
                    action="SEND_LINUX_FAIL",
                    details=f"Failed to send Linux command: {command}",
                    operator=data.get("operator", "Operator"),
                    node=target,
                    status="error"
                )
                return jsonify({
                    "success": False,
                    "error": "Failed to send Linux command"
                }), 500
    except Exception as e:
        logging.error(f"Error in api_linux_commands: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ===== DATA ENDPOINTS (New Format) =====

@app.route('/api/data/fish')
def api_fish_data():
    """Get latest fish detection data"""
    try:
        limit = int(request.args.get('limit', 20))
        if network_state and network_state.cache_initialized:
            data_list = network_state.get_cached_data("fish_detection", limit=limit)
        else:
            data_list = load_latest_data(FISH_DATA_DIR, limit=limit)
        
        return jsonify({
            "success": True,
            "count": len(data_list),
            "data": data_list
        })
    except Exception as e:
        logging.error(f"Error loading fish data: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "data": []
        })


@app.route('/api/data/sonar')
def api_sonar_data():
    """Get latest sonar data"""
    try:
        limit = int(request.args.get('limit', 20))
        if network_state and network_state.cache_initialized:
            data_list = network_state.get_cached_data("sonar_detection", limit=limit)
        else:
            data_list = load_latest_data(SONAR_DATA_DIR, limit=limit)
        
        return jsonify({
            "success": True,
            "count": len(data_list),
            "data": data_list
        })
    except Exception as e:
        logging.error(f"Error loading sonar data: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "data": []
        })


@app.route('/api/data/gps')
def api_gps_data():
    """Get latest GPS data"""
    try:
        limit = int(request.args.get('limit', 20))
        if network_state and network_state.cache_initialized:
            data_list = network_state.get_cached_data("gps", limit=limit)
        else:
            data_list = load_latest_data(GPS_DATA_DIR, limit=limit)
        
        return jsonify({
            "success": True,
            "count": len(data_list),
            "data": data_list
        })
    except Exception as e:
        logging.error(f"Error loading GPS data: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "data": []
        })


@app.route('/api/data/battery')
def api_battery_data():
    """Get latest battery data"""
    try:
        limit = int(request.args.get('limit', 20))
        if network_state and network_state.cache_initialized:
            data_list = network_state.get_cached_data("battery", limit=limit)
            parsed_data = []
            for d in data_list:
                if "cells" in d:
                    parsed_data.append(d)
                else:
                    parsed_data.append(parse_battery_data(d))
        else:
            data_list = load_latest_data(BATTERY_DATA_DIR, limit=limit)
            parsed_data = [parse_battery_data(d) for d in data_list]
        
        return jsonify({
            "success": True,
            "count": len(parsed_data),
            "data": parsed_data
        })
    except Exception as e:
        logging.error(f"Error loading battery data: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "data": []
        })


@app.route('/api/data/commands')
def api_command_results():
    """Get latest command results"""
    try:
        limit = int(request.args.get('limit', 20))
        if network_state and network_state.cache_initialized:
            data_list = network_state.get_cached_data("command_results", limit=limit)
        else:
            data_list = load_latest_data(COMMAND_RESULTS_DIR, limit=limit)
        
        return jsonify({
            "success": True,
            "count": len(data_list),
            "data": data_list
        })
    except Exception as e:
        logging.error(f"Error loading command results: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "data": []
        })


# ===== LEGACY ENDPOINTS (for HTML compatibility) =====

@app.route("/api/fish_data")
def api_fish():
    """Legacy fish endpoint with summary statistics"""
    try:
        limit = int(request.args.get('limit', 50))
        if network_state and network_state.cache_initialized:
            data_list = network_state.get_cached_data("fish_detection", limit=limit)
        else:
            data_list = load_latest_data(FISH_DATA_DIR, limit=limit)
        
        if not data_list:
            logging.warning("⚠ No fish data available")
            return jsonify({
                "success": False,
                "error": "No fish data available",
                "summary": {
                    "total_images": 0,
                    "total_detections": 0,
                    "unique_species": 0,
                    "species_frequency": {}
                },
                "recent_detections": []
            })

        # Flatten list if needed
        data = []
        for item in data_list:
            if isinstance(item, list):
                data.extend(item)
            elif isinstance(item, dict):
                if "records" in item and isinstance(item["records"], list):
                    data.extend(item["records"])
                else:
                    data.append(item)

        total_images = len(data)
        total_detections = sum(int(item.get("Fish Detected", 0) or 0) for item in data if isinstance(item, dict))

        species_counter = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            species_list = item.get("Species Detected", [])
            if species_list and len(species_list) > 0:
                top_species = species_list[0].get("species", "Unknown")
                species_counter[top_species] = species_counter.get(top_species, 0) + 1

        unique_species = len(species_counter)

        logging.info(f"✓ Fish API: {total_images} images, {total_detections} detections, {unique_species} species")
        
        return jsonify({
            "success": True,
            "summary": {
                "total_images": total_images,
                "total_detections": total_detections,
                "unique_species": unique_species,
                "species_frequency": species_counter
            },
            "recent_detections": data[:50]
        })
    
    except Exception as e:
        logging.error(f"✗ Error in api_fish: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "summary": {
                "total_images": 0,
                "total_detections": 0,
                "unique_species": 0,
                "species_frequency": {}
            },
            "recent_detections": []
        })


@app.route("/api/sonar_data")
def api_sonar():
    """Legacy sonar endpoint"""
    try:
        limit = int(request.args.get('limit', 50))
        if network_state and network_state.cache_initialized:
            data_list = network_state.get_cached_data("sonar_detection", limit=limit)
        else:
            data_list = load_latest_data(SONAR_DATA_DIR, limit=limit)
        
        if not data_list:
            logging.warning("⚠ No sonar data available")
            return jsonify({
                "success": False,
                "error": "No sonar data available",
                "total_scans": 0,
                "detections": 0,
                "records": []
            })

        # Flatten list if needed
        data = []
        for item in data_list:
            if isinstance(item, dict):
                if "records" in item and isinstance(item["records"], list):
                    data.extend(item["records"])
                else:
                    data.append(item)

        total_scans = len(data)
        detections = sum(1 for d in data if d.get("Fish Detect", 0) > 0)

        logging.info(f"✓ Sonar API: {total_scans} scans, {detections} detections")
        
        return jsonify({
            "success": True,
            "total_scans": total_scans,
            "detections": detections,
            "records": data
        })
    
    except Exception as e:
        logging.error(f"✗ Error in api_sonar: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "total_scans": 0,
            "detections": 0,
            "records": []
        })


@app.route("/api/gps_data")
def api_gps():
    """Legacy GPS endpoint"""
    try:
        limit = int(request.args.get('limit', 20))
        if network_state and network_state.cache_initialized:
            data_list = network_state.get_cached_data("gps", limit=limit)
        else:
            data_list = load_latest_data(GPS_DATA_DIR, limit=limit)
        
        if not data_list:
            logging.warning("⚠ No GPS data available")
            return jsonify({
                "success": False,
                "error": "No GPS data available",
                "current": {},
                "history": []
            })

        # Get the most recent entry
        latest = data_list[0]
        
        logging.info(f"✓ GPS API: Location at {latest.get('latitude', 'N/A')}, {latest.get('longitude', 'N/A')}")
        
        return jsonify({
            "success": True,
            "current": latest,
            "history": data_list
        })
    
    except Exception as e:
        logging.error(f"✗ Error in api_gps: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "current": {},
            "history": []
        })


@app.route('/api/battery_data')
def api_battery_data_legacy():
    """Legacy endpoint - redirects to new format"""
    try:
        limit = int(request.args.get('limit', 20))
        if network_state and network_state.cache_initialized:
            data_list = network_state.get_cached_data("battery", limit=limit)
            parsed_data = []
            for d in data_list:
                if "cells" in d:
                    parsed_data.append(d)
                else:
                    parsed_data.append(parse_battery_data(d))
        else:
            data_list = load_latest_data(BATTERY_DATA_DIR, limit=limit)
            parsed_data = [parse_battery_data(d) for d in data_list]
        
        return jsonify({
            "success": True,
            "recent_readings": parsed_data
        })
    except Exception as e:
        logging.error(f"Error loading battery data: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "recent_readings": []
        })


@app.route('/api/data/stats')
def api_data_stats():
    """Get statistics about stored data"""
    try:
        if network_state and network_state.cache_initialized:
            stats = {
                "fish_count": network_state.file_counts["fish"],
                "sonar_count": network_state.file_counts["sonar"],
                "gps_count": network_state.file_counts["gps"],
                "battery_count": network_state.file_counts["battery"],
                "command_count": network_state.file_counts["command"]
            }
        else:
            stats = {
                "fish_count": len(list(FISH_DATA_DIR.glob("*.json"))) if FISH_DATA_DIR.exists() else 0,
                "sonar_count": len(list(SONAR_DATA_DIR.glob("*.json"))) if SONAR_DATA_DIR.exists() else 0,
                "gps_count": len(list(GPS_DATA_DIR.glob("*.json"))) if GPS_DATA_DIR.exists() else 0,
                "battery_count": len(list(BATTERY_DATA_DIR.glob("*.json"))) if BATTERY_DATA_DIR.exists() else 0,
                "command_count": len(list(COMMAND_RESULTS_DIR.glob("*.json"))) if COMMAND_RESULTS_DIR.exists() else 0
            }
        
        return jsonify({
            "success": True,
            "stats": stats
        })
    except Exception as e:
        logging.error(f"Error getting data stats: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "stats": {}
        })


# ===== SCHEDULER ENDPOINTS =====

@app.route('/api/schedules', methods=['GET', 'POST', 'DELETE'])
def api_schedules():
    """Manage schedules"""
    try:
        if not scheduler:
            return jsonify({"error": "Scheduler not initialized"}), 500
        
        if request.method == 'GET':
            return jsonify({
                "schedules": scheduler.get_schedules(),
                "next_scheduled": scheduler.get_next_scheduled(limit=5)
            })
        
        elif request.method == 'POST':
            schedule_data = request.json
            schedule_id = scheduler.add_schedule(schedule_data)
            return jsonify({
                "success": True,
                "schedule_id": schedule_id
            })
        
        elif request.method == 'DELETE':
            schedule_id = request.args.get('id')
            if scheduler.remove_schedule(schedule_id):
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Schedule not found"}), 404
    except Exception as e:
        logging.error(f"Error in api_schedules: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/scheduler/toggle/<schedule_id>', methods=['POST'])
def api_toggle_schedule(schedule_id):
    """Toggle schedule enabled/disabled"""
    try:
        if not scheduler:
            return jsonify({"error": "Scheduler not initialized"}), 500
        
        if scheduler.toggle_schedule(schedule_id):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Schedule not found"}), 404
    except Exception as e:
        logging.error(f"Error in api_toggle_schedule: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/send_command', methods=['POST'])
def send_command():
    """
    Send manual command to BUOY node
    CRITICAL FIX: Uses transmission queue to prevent race conditions
    """
    try:
        data = request.json
        target = data.get('target')
        scripts = data.get('scripts', [])
        args_dict = data.get('args', {})
        
        if not target or not scripts:
            return jsonify({"success": False, "error": "Missing target or scripts"}), 400
        
        from logic import send_command_to_buoy
        
        # CRITICAL FIX: Queue the command instead of sending directly
        scheduler.queue_manual_command(
            send_command_to_buoy,
            network_state,
            lora_controller,
            target,
            scripts,
            args_dict
        )
        
        return jsonify({
            "success": True,
            "message": "Command queued for transmission",
            "target": target,
            "scripts": scripts
        })
        
    except Exception as e:
        logger.error(f"[API] Send command error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """Get scheduler and transmission queue status"""
    try:
        status = scheduler.get_transmission_status()
        return jsonify({
            "success": True,
            "status": status
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ===== SETTINGS ENDPOINTS =====

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update settings"""
    settings_file = DATA_DIR / "settings.json"
    
    if request.method == 'GET':
        try:
            import config
            import importlib
            importlib.reload(config)
            
            settings = load_json_data(settings_file) or {}
            settings.update({
                "discovery_interval": config.DISCOVERY_INTERVAL,
                "neighbor_timeout": config.NEIGHBOR_TIMEOUT,
                "active_list": config.ACTIVE_BUOY_LIST
            })
            
            return jsonify(settings)
        except Exception as e:
            logging.error(f"Error loading settings: {e}")
            return jsonify({})
    
    elif request.method == 'POST':
        settings = request.json
        
        if 'active_list' in settings:
            active_list = settings['active_list']
            if update_config_file(active_list):
                try:
                    import config
                    import importlib
                    importlib.reload(config)
                    
                    if network_state:
                        network_state.update_active_list(active_list)
                        logging.info(f"Updated active list: {active_list}")
                except:
                    pass
        
        if save_json_data(settings, settings_file, add_timestamp=False):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to save"}), 500

# ===== ANALYTICS API ENDPOINTS =====

@app.route('/api/analytics/summary')
def api_analytics_summary():
    """Get timeline summary for configured number of days"""
    try:
        if not ANALYTICS_AVAILABLE or not daily_aggregator:
            return jsonify({
                "success": False,
                "error": "Analytics not available"
            }), 503
        
        days = request.args.get('days', type=int)
        timeline = daily_aggregator.get_or_create_timeline(days)
        
        return jsonify({
            "success": True,
            "timeline": timeline
        })
    except Exception as e:
        logging.error(f"Error in analytics summary: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/analytics/daily/<date_str>')
def api_analytics_daily(date_str):
    """Get analysis for a specific date (YYYY-MM-DD)"""
    try:
        if not ANALYTICS_AVAILABLE or not daily_aggregator:
            return jsonify({
                "success": False,
                "error": "Analytics not available"
            }), 503
        
        # Parse date
        date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Get or create daily summary
        summary = daily_aggregator.load_daily_summary(date)
        
        if not summary:
            summary = daily_aggregator.create_daily_summary(date)
        
        return jsonify({
            "success": True,
            "summary": summary
        })
    except ValueError:
        return jsonify({
            "success": False,
            "error": "Invalid date format. Use YYYY-MM-DD"
        }), 400
    except Exception as e:
        logging.error(f"Error in daily analytics: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/analytics/predict/<date_str>')
def api_analytics_predict(date_str):
    """Get prediction for a specific future date (YYYY-MM-DD)"""
    try:
        if not ANALYTICS_AVAILABLE or not prediction_service:
            return jsonify({
                "success": False,
                "error": "Prediction service not available"
            }), 503
        
        # Parse date
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Check if prediction already exists
        prediction_file = PREDICTIONS_DIR / f"prediction_{date_str}.json"
        
        if prediction_file.exists():
            prediction = load_json_data(prediction_file)
        else:
            # Generate new prediction
            historical_days = request.args.get('historical_days', type=int, default=30)
            prediction = prediction_service.generate_prediction(target_date, historical_days)
        
        return jsonify({
            "success": True,
            "prediction": prediction
        })
    except ValueError:
        return jsonify({
            "success": False,
            "error": "Invalid date format. Use YYYY-MM-DD"
        }), 400
    except Exception as e:
        logging.error(f"Error in prediction: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/analytics/aggregate', methods=['POST'])
def api_analytics_aggregate():
    """Manually trigger daily aggregation"""
    try:
        if not ANALYTICS_AVAILABLE or not daily_aggregator:
            return jsonify({
                "success": False,
                "error": "Analytics not available"
            }), 503
        
        # Run aggregation
        import config as cfg
        run_daily_aggregation(cfg)
        
        return jsonify({
            "success": True,
            "message": "Daily aggregation completed"
        })
    except Exception as e:
        logging.error(f"Error in manual aggregation: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/feedback', methods=['POST'])
def api_feedback():
    """Submit operator feedback"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        feedback_file = DATA_DIR / "feedback.json"
        
        existing = []
        if feedback_file.exists():
            existing_data = load_json_data(feedback_file)
            if isinstance(existing_data, list):
                existing = existing_data
                
        new_entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.utcnow().isoformat(),
            "operator": data.get("operator", "Anonymous"),
            "category": data.get("category", "General"),
            "rating": data.get("rating", 5),
            "message": data.get("message", ""),
            "page": data.get("page", "Unknown")
        }
        existing.append(new_entry)
        
        save_json_data(existing, feedback_file, add_timestamp=False)
        
        return jsonify({
            "success": True,
            "message": "Feedback submitted successfully",
            "feedback": new_entry
        })
    except Exception as e:
        logging.error(f"Error in api_feedback: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/audit_log', methods=['GET', 'POST'])
def api_audit_log():
    """Get or write audit log trace records"""
    try:
        audit_file = DATA_DIR / "audit_log.json"
        
        existing = []
        if audit_file.exists():
            existing_data = load_json_data(audit_file)
            if isinstance(existing_data, list):
                existing = existing_data
                
        if request.method == 'GET':
            sorted_logs = sorted(existing, key=lambda x: x.get("timestamp", ""), reverse=True)
            return jsonify({
                "success": True,
                "logs": sorted_logs[:50]
            })
            
        elif request.method == 'POST':
            data = request.json
            if not data:
                return jsonify({"success": False, "error": "No log data provided"}), 400
                
            new_log = {
                "timestamp": datetime.utcnow().isoformat(),
                "action": data.get("action", "unknown"),
                "operator": data.get("operator", "System"),
                "details": data.get("details", ""),
                "status": data.get("status", "info"),
                "node": data.get("node", "N/A")
            }
            existing.append(new_log)
            save_json_data(existing, audit_file, add_timestamp=False)
            
            return jsonify({
                "success": True,
                "log": new_log
            })
    except Exception as e:
        logging.error(f"Error in api_audit_log: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ===== WEB PAGE ROUTES =====

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/networks/')
def dashboard():
    return render_template('networks/index.html')

@app.route('/commands/')
def commands():
    return render_template('commands/index.html')

@app.route('/linux_commands/')
def linux_commands():
    return render_template('commands/linux.html')

@app.route('/scheduler/')
def scheduler_page():
    return render_template('scheduler/index.html')

@app.route('/monitors/fish/')
def fish_monitor():
    return render_template('monitors/fish.html')

@app.route('/prediction/')
def prediction_page():
    return render_template('monitors/prediction.html')

@app.route('/monitors/sonar/')
def sonar_monitor():
    return render_template('monitors/sonar.html')

@app.route('/monitors/gps/')
def gps_monitor():
    return render_template('monitors/gps.html')

@app.route('/monitors/battery/')
def battery_monitor():
    return render_template('monitors/battery.html')

@app.route('/settings/')
def settings():
    return render_template('settings/index.html')


# ===== SERVER STARTUP =====

def run_server(state, controller, sched):
    """Initialize and run the Flask server"""
    global network_state, lora_controller, scheduler
    network_state = state
    lora_controller = controller
    scheduler = sched
    
    try:
        from waitress import serve
        logging.info(f"🌐 Starting web server on http://{SERVER_HOST}:{SERVER_PORT} using Waitress (Production)")
        serve(app, host=SERVER_HOST, port=SERVER_PORT, threads=64)
    except ImportError:
        logging.warning("⚠️ Waitress is not installed. Falling back to Flask development server.")
        app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, threaded=True)


if __name__ == '__main__':
    logging.info("="*60)
    logging.info("BASE Station Web Server - Standalone Mode")
    logging.info("="*60)
    
    try:
        from waitress import serve
        logging.info(f"🌐 Starting server on http://{SERVER_HOST}:{SERVER_PORT} using Waitress (Production)")
        logging.info("="*60)
        serve(app, host=SERVER_HOST, port=SERVER_PORT, threads=64)
    except ImportError:
        logging.warning("⚠️ Waitress is not installed. Falling back to Flask development server.")
        logging.info(f"🌐 Starting server on http://{SERVER_HOST}:{SERVER_PORT}")
        logging.info("="*60)
        app.run(host=SERVER_HOST, port=SERVER_PORT, debug=True)
