#!/usr/bin/env python3
import json
import time
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from collections import deque
from config import *
from utils import *

logger = logging.getLogger("LoRaController")


class NetworkState:
    """Global network state management with enhanced chunk reception tracking"""
    
    def __init__(self):
        # Active List - expected nodes (Dynamic)
        self.active_list = {node: {"expected": True} for node in ACTIVE_BUOY_LIST}
        
        # Neighbor Table - nodes that have responded
        self.neighbor_table = {}
        
        # Tracking structures
        self.chunk_buffer = {}
        self.seen_messages = {}
        self.seen_messages_lru = deque(maxlen=MAX_SEEN_MESSAGES)
        self.pending_acks = {}
        
        # Command tracking
        self.active_commands = {}
        self.active_linux_commands = {}
        
        # Statistics
        self.stats = {key: 0 for key in STATS_KEYS}
        
        # Locks
        self.chunk_lock = threading.Lock()
        self.seen_lock = threading.Lock()
        self.neighbor_lock = threading.Lock()
        self.command_lock = threading.Lock()
        self.linux_command_lock = threading.Lock()
        self.active_list_lock = threading.Lock()
        self.transmission_lock = threading.Lock()
        
        # CRITICAL FIX: Track active chunk reception
        self.receiving_chunks = {}  # {sender: last_chunk_time}
        self.chunk_reception_lock = threading.Lock()

        # In-memory caches for web server speedup
        self.caches = {
            "fish_detection": [],
            "sonar_detection": [],
            "gps": [],
            "battery": [],
            "command_status": [],
            "linux_command": [],
            "command_results": []
        }
        self.file_counts = {
            "fish": 0,
            "sonar": 0,
            "gps": 0,
            "battery": 0,
            "command": 0
        }
        self.cache_lock = threading.Lock()
        self.cache_initialized = False

    def init_caches_from_disk(self):
        """Pre-populate caches from disk on startup (called once)"""
        with self.cache_lock:
            if self.cache_initialized:
                return
            
            # Map of cache name to directory
            dir_mapping = {
                "fish_detection": FISH_DATA_DIR,
                "sonar_detection": SONAR_DATA_DIR,
                "gps": GPS_DATA_DIR,
                "battery": BATTERY_DATA_DIR,
                "command_status": COMMAND_RESULTS_DIR / "command_status",
                "linux_command": COMMAND_RESULTS_DIR / "linux_commands",
                "command_results": COMMAND_RESULTS_DIR
            }
            
            from utils import load_json_data
            
            for cache_key, directory in dir_mapping.items():
                if not directory.exists():
                    continue
                
                try:
                    # Get files sorted by mtime, limit to latest 50 for caching
                    json_files = list(directory.glob("*.json"))
                    json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    
                    # Update count
                    count_key = {
                        "fish_detection": "fish",
                        "sonar_detection": "sonar",
                        "gps": "gps",
                        "battery": "battery"
                    }.get(cache_key, "command")
                    self.file_counts[count_key] += len(json_files)
                    
                    for filepath in json_files[:50]:
                        data = load_json_data(filepath)
                        if data is not None:
                            # Normalize structure
                            if isinstance(data, list):
                                record = {
                                    "records": data,
                                    "_filename": filepath.name,
                                    "_filepath": str(filepath)
                                }
                            elif isinstance(data, dict):
                                data["_filename"] = filepath.name
                                data["_filepath"] = str(filepath)
                                record = data
                            else:
                                continue
                            
                            self.caches[cache_key].append(record)
                            
                except Exception as e:
                    logger.error(f"[CACHE] Error populating {cache_key} cache: {e}")
            
            self.cache_initialized = True
            logger.info("[CACHE] Pre-populated in-memory caches from disk successfully")

    def add_to_cache(self, data_type: str, data: Dict[str, Any]):
        """Add a new record to the in-memory cache and maintain limit"""
        with self.cache_lock:
            cache_key = data_type
            if cache_key not in self.caches:
                self.caches[cache_key] = []
            
            # Insert at the beginning (newest first)
            self.caches[cache_key].insert(0, data)
            
            # Limit to 100 entries
            if len(self.caches[cache_key]) > 100:
                self.caches[cache_key] = self.caches[cache_key][:100]
                
            # Update counts
            count_key = {
                "fish_detection": "fish",
                "sonar_detection": "sonar",
                "gps": "gps",
                "battery": "battery"
            }.get(cache_key, "command")
            self.file_counts[count_key] += 1

    def get_cached_data(self, cache_key: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get latest records from the in-memory cache"""
        with self.cache_lock:
            if not self.cache_initialized:
                # Initialize caches if not done yet
                self.init_caches_from_disk()
            
            records = self.caches.get(cache_key, [])
            return list(records[:limit])

    def is_receiving_chunks(self) -> bool:
        """
        Check if we're currently receiving chunks from any node
        Returns True if any chunk was received in the last 5 seconds
        """
        current_time = time.time()
        with self.chunk_reception_lock:
            # Clean up old entries
            expired = [sender for sender, last_time in self.receiving_chunks.items()
                      if current_time - last_time > 5.0]
            for sender in expired:
                del self.receiving_chunks[sender]
            
            # Return True if any recent chunk activity
            return len(self.receiving_chunks) > 0
    
    def mark_chunk_received(self, sender: str):
        """Mark that we just received a chunk from a sender"""
        with self.chunk_reception_lock:
            self.receiving_chunks[sender] = time.time()
    
    def update_neighbor(self, sender: str, hops: Optional[int] = None, 
                       direct: bool = False, rssi: Optional[int] = None):
        """Update neighbor information"""
        current_time = time.time()
        
        with self.neighbor_lock:
            if sender not in self.neighbor_table:
                self.neighbor_table[sender] = {
                    "codename": sender,
                    "last_seen": current_time,
                    "last_direct": None,
                    "hops": hops if hops is not None else 999,
                    "rssi": rssi,
                    "status": "ONLINE"
                }
            
            self.neighbor_table[sender]["last_seen"] = current_time
            
            if direct:
                self.neighbor_table[sender]["last_direct"] = current_time
                self.neighbor_table[sender]["hops"] = 0
            elif hops is not None:
                if hops < self.neighbor_table[sender]["hops"]:
                    self.neighbor_table[sender]["hops"] = hops
            
            if rssi is not None:
                self.neighbor_table[sender]["rssi"] = rssi
            
            # Update status
            self.neighbor_table[sender]["status"] = get_node_status(
                self.neighbor_table[sender], current_time
            )
    
    def is_duplicate(self, sender: str, msg_id: str, 
                    parent_id: Optional[str] = None, 
                    seq: Optional[int] = None) -> bool:
        """Check if message has been seen before"""
        current_time = time.time()
        
        if parent_id is not None and seq is not None:
            key = (sender, parent_id, seq)
        else:
            key = (sender, msg_id)
        
        with self.seen_lock:
            if key in self.seen_messages:
                if current_time - self.seen_messages[key] < 300:
                    self.stats["duplicates_dropped"] += 1
                    return True
                else:
                    del self.seen_messages[key]
            
            self.seen_messages[key] = current_time
            self.seen_messages_lru.append(key)
            
            # Cleanup old entries
            if len(self.seen_messages) > MAX_SEEN_MESSAGES:
                cutoff_time = current_time - 300
                to_remove = [k for k, t in self.seen_messages.items() if t < cutoff_time]
                for k in to_remove[:MAX_SEEN_MESSAGES // 4]:
                    if k in self.seen_messages:
                        del self.seen_messages[k]
        
        return False
    
    def cleanup_stale_neighbors(self):
        """Remove neighbors that haven't been seen recently"""
        current_time = time.time()
        
        with self.neighbor_lock:
            stale = [n for n, info in self.neighbor_table.items() 
                    if current_time - info["last_seen"] > NEIGHBOR_TIMEOUT]
            
            for n in stale:
                del self.neighbor_table[n]
                logger.warning(f"⚠ Removed stale neighbor {n}")
    
    def get_neighbor_summary(self) -> Dict[str, Any]:
        """Get summary of neighbor table"""
        with self.neighbor_lock:
            current_time = time.time()
            direct = sum(1 for info in self.neighbor_table.values() 
                        if info.get("last_direct") is not None)
            relay = len(self.neighbor_table) - direct
            
            return {
                "total": len(self.neighbor_table),
                "direct": direct,
                "relay": relay,
                "neighbors": dict(self.neighbor_table)
            }
    
    def get_active_list_status(self) -> List[Dict[str, Any]]:
        """Get status of all nodes in active list"""
        current_time = time.time()
        status_list = []
        
        with self.active_list_lock:
            active_nodes = list(self.active_list.keys())
        
        with self.neighbor_lock:
            for node in active_nodes:
                if node in self.neighbor_table:
                    info = self.neighbor_table[node]
                    status_list.append({
                        "codename": node,
                        "status": get_node_status(info, current_time),
                        "last_seen": info.get("last_seen"),
                        "hops": info.get("hops", "N/A"),
                        "rssi": info.get("rssi"),
                        "signal": calculate_signal_strength(info.get("rssi"))
                    })
                else:
                    status_list.append({
                        "codename": node,
                        "status": "UNREACHABLE",
                        "last_seen": None,
                        "hops": "N/A",
                        "rssi": None,
                        "signal": "Unknown"
                    })
        
        return status_list
    
    def update_active_list(self, new_active_list: List[str]):
        """Update the active list dynamically"""
        with self.active_list_lock:
            self.active_list = {node: {"expected": True} for node in new_active_list}
            logger.info(f"✓ Active list updated: {new_active_list}")
    
    def track_command(self, command_id: str, target: str, 
        scripts: List[str]) -> None:
        """Track a sent command"""
        with self.command_lock:
            self.active_commands[command_id] = {
                "command_id": command_id,
                "target": target,
                "scripts": scripts,
                "status": {},
                "results": {},
                "sent_at": time.time(),
                "ack_received": False
            }
            
            for script in scripts:
                self.active_commands[command_id]["status"][script] = "PENDING"
                self.active_commands[command_id]["results"][script] = None
    
    def update_command_ack(self, command_id: str) -> None:
        """Update command ACK status"""
        with self.command_lock:
            if command_id in self.active_commands:
                self.active_commands[command_id]["ack_received"] = True
                logger.info(f"✓ Command {command_id} acknowledged")
    
    def update_command_status(self, command_id: str, script: str, 
                            status: str, exit_code: int = 0) -> None:
        """Update command execution status"""
        with self.command_lock:
            if command_id in self.active_commands:
                self.active_commands[command_id]["status"][script] = status
                
                # Check if all scripts completed
                all_completed = all(
                    s in ["COMPLETED", "FAILED"] 
                    for s in self.active_commands[command_id]["status"].values()
                )
                
                if all_completed:
                    self.stats["commands_completed"] += 1
                    logger.info(f"✓ Command {command_id} completed")
    
    def track_linux_command(self, command_id: str, target: str, command: str) -> None:
        """Track a sent Linux command"""
        with self.linux_command_lock:
            self.active_linux_commands[command_id] = {
                "command_id": command_id,
                "target": target,
                "command": command,
                "status": "PENDING",
                "output": None,
                "exit_code": None,
                "sent_at": time.time(),
                "completed_at": None,
                "ack_received": False
            }
    
    def update_linux_command_ack(self, command_id: str) -> None:
        """Update Linux command ACK status"""
        with self.linux_command_lock:
            if command_id in self.active_linux_commands:
                self.active_linux_commands[command_id]["ack_received"] = True
                logger.info(f"✓ Linux command {command_id} acknowledged")
    
    def update_linux_command_status(self, command_id: str, exit_code: int, 
                                   feedback_type: str, output: str) -> None:
        """
        Update Linux command execution status
        FIXED: Properly mark command as completed
        """
        with self.linux_command_lock:
            if command_id in self.active_linux_commands:
                if feedback_type == "error":
                    status = "FAILED"
                elif feedback_type in ["result", "output"]:
                    status = "COMPLETED"
                else:
                    status = feedback_type.upper()
                
                self.active_linux_commands[command_id]["status"] = status
                self.active_linux_commands[command_id]["output"] = output
                self.active_linux_commands[command_id]["exit_code"] = exit_code
                self.active_linux_commands[command_id]["completed_at"] = time.time()
                
                if status in ["COMPLETED", "FAILED"]:
                    self.stats["commands_completed"] += 1
                    logger.info(f"✓ Linux command {command_id} {status.lower()}")
    
    def get_all_commands(self) -> List[Dict[str, Any]]:
        """Get all active commands"""
        with self.command_lock:
            return [
                {
                    "command_id": cmd_id,
                    "target": info["target"],
                    "scripts": info["scripts"],
                    "status": info["status"],
                    "results": info["results"],
                    "ack_received": info["ack_received"],
                    "sent_at": format_timestamp(info["sent_at"])
                }
                for cmd_id, info in self.active_commands.items()
            ]
    
    def get_all_linux_commands(self) -> List[Dict[str, Any]]:
        """Get all active Linux commands"""
        with self.linux_command_lock:
            return [
                {
                    "command_id": cmd_id,
                    "target": info["target"],
                    "command": info["command"],
                    "status": info["status"],
                    "output": info["output"],
                    "exit_code": info["exit_code"],
                    "ack_received": info["ack_received"],
                    "sent_at": format_timestamp(info["sent_at"]),
                    "completed_at": format_timestamp(info["completed_at"]) if info["completed_at"] else None
                }
                for cmd_id, info in self.active_linux_commands.items()
            ]


def cleanup_chunk_buffer(state: NetworkState):
    """Remove incomplete chunks that have timed out"""
    current_time = time.time()
    purged_count = 0
    total_chunks_lost = 0
    
    with state.chunk_lock:
        to_delete = []
        for key, buffer in state.chunk_buffer.items():
            if current_time - buffer.get("last_seen", 0) > CHUNK_TIMEOUT:
                to_delete.append(key)
                chunks_received = len(buffer.get("chunks", {}))
                total_expected = buffer.get("total", 0)
                total_chunks_lost += (total_expected - chunks_received)
        
        for key in to_delete:
            del state.chunk_buffer[key]
            purged_count += 1
        
        if purged_count > 0:
            logger.warning(f"⚠ Purged {purged_count} incomplete transmissions ({total_chunks_lost} chunks lost)")
    
    return purged_count


def save_received_data(data: Dict[str, Any], sender: str, data_type: str, state: Optional['NetworkState'] = None) -> bool:
    """
    Save received data to appropriate directory
    CRITICAL FIX: Enhanced error handling, logging, and validation
    FIXED: Proper fish detection data categorization
    FIXED: Command status saved to dedicated folder
    """
    try:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"[SAVE] [-] Processing {data_type} data from {sender}")
        
        # CRITICAL FIX: Log the data structure for debugging
        if isinstance(data, dict):
            logger.debug(f"[SAVE]   → Data keys: {list(data.keys())}")
            logger.debug(f"[SAVE]   → Data size: {len(json.dumps(data))} bytes")
        
        # ===== DETERMINE SAVE DIRECTORY =====
        save_dir = None
        filename = None
        
        # FIXED: Better fish detection data categorization
        # Check for fish detection data with more specific patterns
        data_str = json.dumps(data) if isinstance(data, dict) else str(data)
        data_str_lower = data_str.lower()
        
        if (data_type == "fish_detection" or 
            "species detected" in data_str_lower or
            "fish_species" in data_str_lower or
            ("fish" in data_str_lower and "detected" in data_str_lower) or
            ("species" in data_str_lower and "confidence" in data_str_lower) or
            "yolo" in data_str_lower or
            "detection_results" in data_str_lower):
            save_dir = FISH_DATA_DIR
            filename = f"{sender}_{timestamp}_fish.json"
            logger.info(f"[SAVE] 🐟 Categorized as fish detection data")
        
        # Check for sonar data
        elif (data_type == "sonar_detection" or 
              "Fish Detect" in data_str or 
              "sonar" in data_str_lower or
              "ping" in data_str_lower):
            save_dir = SONAR_DATA_DIR
            filename = f"{sender}_{timestamp}_sonar.json"
            logger.info(f"[SAVE] 📡 Categorized as sonar detection data")
        
        # Check for GPS data
        elif (data_type == "gps" or 
              data_type == MSG_TYPE_GPS or
              "latitude" in data_str_lower or 
              "longitude" in data_str_lower or
              "GPS" in data_str or
              ("lat" in data and isinstance(data, dict)) or 
              ("lon" in data and isinstance(data, dict))):
            save_dir = GPS_DATA_DIR
            filename = f"{sender}_{timestamp}_gps.json"
            logger.info(f"[SAVE] 📍 Categorized as GPS data")
        
        # Check for battery data
        elif (data_type == "battery" or 
              data_type == MSG_TYPE_BATTERY or
              "charge_state" in data_str_lower or 
              "voltage_v" in data_str_lower or
              "cells" in data_str_lower or
              ("battery" in data_str_lower and "voltage" in data_str_lower)):
            save_dir = BATTERY_DATA_DIR
            filename = f"{sender}_{timestamp}_battery.json"
            logger.info(f"[SAVE] 🔋 Categorized as battery data")
        
        # FIXED: Command status gets its own dedicated folder
        elif (data_type == "command_status" or 
              ("script" in data and isinstance(data, dict)) or
              ("cmd_status" in data_str_lower and "command_id" in data_str_lower)):
            save_dir = COMMAND_RESULTS_DIR / "command_status"
            filename = f"{sender}_{timestamp}_cmd_status.json"
            logger.info(f"[SAVE] 📊 Categorized as command status (separate from results)")
        
        # Check for Linux command results
        elif (data_type == "linux_command" or 
              ("command" in data and isinstance(data, dict)) or 
              ("exit_code" in data and isinstance(data, dict)) or
              ("output" in data and isinstance(data, dict)) or
              "stdout" in data_str_lower or
              "stderr" in data_str_lower):
            save_dir = COMMAND_RESULTS_DIR / "linux_commands"
            filename = f"{sender}_{timestamp}_linux_cmd.json"
            logger.info(f"[SAVE] 🖥️ Categorized as Linux command result (separate from status)")
        
        # Check for scheduled command results
        elif "schedule_id" in data_str_lower or "scheduled" in data_str_lower:
            save_dir = COMMAND_RESULTS_DIR / "scheduled_results"
            filename = f"{sender}_{timestamp}_scheduled_result.json"
            logger.info(f"[SAVE] ⏰ Categorized as scheduled command result")
        
        # Check for data type in packet
        elif isinstance(data, dict) and "type" in data:
            packet_type = data.get("type")
            if packet_type == MSG_TYPE_GPS or packet_type == "gps":
                save_dir = GPS_DATA_DIR
                filename = f"{sender}_{timestamp}_gps.json"
                logger.info(f"[SAVE] 📍 Categorized by packet type: GPS")
            elif packet_type == MSG_TYPE_BATTERY or packet_type == "battery":
                save_dir = BATTERY_DATA_DIR
                filename = f"{sender}_{timestamp}_battery.json"
                logger.info(f"[SAVE] 🔋 Categorized by packet type: Battery")
            else:
                # FIXED: Generic payload data goes to its own folder
                save_dir = RECEIVED_DATA_DIR / "payload"
                filename = f"{sender}_{timestamp}_{packet_type}.json"
                logger.info(f"[SAVE] [-] Categorized by packet type: {packet_type}")
        
        # Default: save to general payload folder (not command results)
        else:
            save_dir = RECEIVED_DATA_DIR / "payload"
            filename = f"{sender}_{timestamp}_data.json"
            logger.warning(f"[SAVE] ⚠️ Could not categorize data, using payload folder")
            logger.warning(f"[SAVE]   → Data type: {data_type}")
            logger.warning(f"[SAVE]   → Data preview: {str(data)[:200]}...")
        
        # CRITICAL FIX: Validate save directory and filename
        if save_dir is None or filename is None:
            logger.error(f"[SAVE] ❌ Failed to determine save location for {data_type} from {sender}")
            return False
        
        # CRITICAL FIX: Ensure directory exists with proper error handling
        try:
            save_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"[SAVE]   → Directory: {save_dir}")
        except Exception as e:
            logger.error(f"[SAVE] ❌ Failed to create directory {save_dir}: {e}")
            return False
        
        # CRITICAL FIX: Add comprehensive metadata
        if isinstance(data, dict):
            # Don't modify original data, create a copy
            data_to_save = data.copy()
            data_to_save["_metadata"] = {
                "received_from": sender,
                "received_at": time.time(),
                "received_at_readable": datetime.utcnow().isoformat(),
                "data_type": data_type,
                "saved_to": str(save_dir / filename),
                "categorization_method": "automatic",
                "base_station": CODENAME
            }
        else:
            data_to_save = data
        
        filepath = save_dir / filename
        
        # CRITICAL FIX: Use enhanced save function with detailed logging
        from utils import save_json_data
        
        logger.info(f"[SAVE] 💾 Writing to: {filepath}")
        success = save_json_data(data_to_save, filepath, add_timestamp=True)
        
        if success:
            # Verify file was actually created
            if filepath.exists():
                file_size = filepath.stat().st_size
                logger.info(f"[SAVE] ✅ Successfully saved {data_type} data")
                logger.info(f"[SAVE]   → File: {filename}")
                logger.info(f"[SAVE]   → Size: {file_size} bytes")
                logger.info(f"[SAVE]   → Path: {filepath}")
                
                # Update in-memory cache
                if state:
                    state.add_to_cache(data_type, data_to_save)
                
                return True
            else:
                logger.error(f"[SAVE] ❌ File not found after save: {filepath}")
                return False
        else:
            logger.error(f"[SAVE] ❌ save_json_data returned False for {filename}")
            return False
        
    except Exception as e:
        logger.error(f"[SAVE] ❌ Exception in save_received_data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def validate_data_directories():
    """
    Validate all data directories exist and are writable
    Call this on BASE station startup
    FIXED: Added subdirectories for better organization
    """
    directories = [
        ("Received Data", RECEIVED_DATA_DIR),
        ("Received Data - Payload", RECEIVED_DATA_DIR / "payload"),
        ("Fish Data", FISH_DATA_DIR),
        ("Sonar Data", SONAR_DATA_DIR),
        ("GPS Data", GPS_DATA_DIR),
        ("Battery Data", BATTERY_DATA_DIR),
        ("Command Results", COMMAND_RESULTS_DIR),
        ("Command Results - Status", COMMAND_RESULTS_DIR / "command_status"),
        ("Command Results - Linux", COMMAND_RESULTS_DIR / "linux_commands"),
        ("Command Results - Scheduled", COMMAND_RESULTS_DIR / "scheduled_results"),
    ]
    
    logger.info("="*60)
    logger.info("VALIDATING DATA DIRECTORIES")
    logger.info("="*60)
    
    all_valid = True
    for name, directory in directories:
        try:
            # Create directory
            directory.mkdir(parents=True, exist_ok=True)
            
            # Test write permissions
            test_file = directory / ".write_test"
            with open(test_file, 'w') as f:
                f.write("test")
            test_file.unlink()
            
            logger.info(f"✅ {name}: {directory}")
            
        except Exception as e:
            logger.error(f"❌ {name}: {directory}")
            logger.error(f"   Error: {e}")
            all_valid = False
    
    logger.info("="*60)
    
    if all_valid:
        logger.info("✅ All data directories validated successfully")
    else:
        logger.error("❌ Some data directories failed validation")
        logger.error("    Data saving may not work properly!")
    
    logger.info("="*60)
    
    return all_valid

def process_message(state: 'NetworkState', lora_controller, 
                   message: str, parse_depth: int = 0, scheduler=None):
    """
    Parse and process received messages
    CRITICAL FIX: Marks reception for half-duplex coordination
    FIXED: Proper detection and saving of fish detection data from capture payload
    FIXED: Sonar data is now properly saved after reassembly
    
    Parameters:
        scheduler: CommandScheduler instance for half-duplex coordination
    """
    if parse_depth > 5:
        logger.error("[X] Max parse depth exceeded - possible recursion")
        return
    
    try:
        packet = json.loads(message)
        
        # Validate that packet is a dictionary, not a list or other type
        if not isinstance(packet, dict):
            logger.error(f"[X] Invalid packet format: expected dict, got {type(packet).__name__}")
            logger.debug(f"   Received: {str(packet)[:200]}")
            return
        
        sender = packet.get("from", "Unknown")
        msg_id = packet.get("msg_id")
        cmd_type = packet.get("type")
        to = packet.get("to")
        via = packet.get("via", [])
        rssi = packet.get("rssi")
        
        state.stats["packets_received"] += 1
        
        hops = len(via) if via else 0
        is_direct = len(via) == 0
        
        state.update_neighbor(sender, hops=hops, direct=is_direct, rssi=rssi)
        
        # ===== CHUNK HANDLING - CRITICAL SECTION =====
        if cmd_type == MSG_TYPE_CHUNK:
            # CRITICAL FIX: Mark chunk reception for half-duplex coordination
            if scheduler:
                scheduler.tx_queue.mark_reception('chunk')
            
            parent_id = packet.get("parent_id")
            seq = packet.get("seq")
            total = packet.get("total")
            
            # Mark that we're receiving chunks (for is_receiving_chunks check)
            state.mark_chunk_received(sender)
            
            # Deduplication for chunks
            if state.is_duplicate(sender, msg_id, parent_id=parent_id, seq=seq):
                logger.debug(f"⊗ Duplicate chunk from {sender}")
                return
            
            logger.info(f"[-] Received chunk {seq+1}/{total} from {sender}")
            
            # Try to reassemble (no ACK sent back)
            from logic import reassemble_chunks
            reassembled = reassemble_chunks(state, sender, packet)
            if reassembled:
                logger.info(f"✓ Reassembled complete transmission from {sender}")
                
                # CRITICAL FIX: Extract actual data from reassembled wrapper
                actual_data = reassembled
                data_type_hint = "data"
                
                # Check if wrapped in reassembled_data structure
                if isinstance(reassembled, dict) and "type" in reassembled:
                    if reassembled.get("type") == "reassembled_data":
                        # Unwrap the payload
                        actual_data = reassembled.get("payload", reassembled)
                        logger.info(f"[-] Unwrapped reassembled_data payload")
                
                # CRITICAL FIX: Detect data type from reassembled content
                data_str = json.dumps(actual_data).lower()
                
                # Fish detection patterns
                is_fish_data = (
                    "species detected" in data_str or
                    "fish_species" in data_str or
                    ("fish" in data_str and "detected" in data_str) or
                    ("species" in data_str and "confidence" in data_str) or
                    "yolo" in data_str or
                    "detection_results" in data_str or
                    ("capture" in data_str and ("fish" in data_str or "species" in data_str))
                )
                
                # CRITICAL FIX: Sonar detection patterns
                is_sonar_data = (
                    "Fish Detect" in json.dumps(actual_data) or
                    "sonar" in data_str or
                    "ping" in data_str or
                    ("distance" in data_str and "depth" in data_str)
                )
                
                # Check if this is a Linux command result
                is_linux_result = (
                    "command" in reassembled or 
                    "exit_code" in reassembled or
                    ("output" in reassembled and not is_fish_data and not is_sonar_data) or
                    "linux_cmd_result" in data_str
                )
                
                if is_fish_data:
                    logger.info(f"🐟 Identified as fish detection data from {sender}")
                    from logic import save_received_data
                    save_received_data(actual_data, sender, "fish_detection", state)
                    
                # CRITICAL FIX: Save sonar data after reassembly
                elif is_sonar_data:
                    logger.info(f"📡 Identified as sonar detection data from {sender}")
                    from logic import save_received_data
                    save_received_data(actual_data, sender, "sonar_detection", state)
                    
                elif is_linux_result:
                    logger.info(f"🖥️ Identified as Linux command result from {sender}")
                    
                    # Update command status if command_id is present
                    command_id = reassembled.get("command_id")
                    if command_id:
                        exit_code = reassembled.get("exit_code", 0)
                        output = reassembled.get("output", "") or reassembled.get("error", "")
                        feedback_type = "result" if "output" in reassembled else "error"
                        
                        state.update_linux_command_status(command_id, exit_code, feedback_type, output)
                    
                    # Save as Linux command result
                    from logic import save_received_data
                    save_received_data(reassembled, sender, "linux_command", state)
                else:
                    # Process as regular message
                    process_message(
                        state,
                        lora_controller,
                        json.dumps(reassembled),
                        parse_depth + 1,
                        scheduler  # Pass scheduler for recursive calls
                    )
            
            return
        
        # ===== REGULAR ACK HANDLING =====
        elif cmd_type == MSG_TYPE_ACK:
            ack_msg_id = packet.get("ack_msg_id")
            logger.info(f"✓ ACK from {sender} for message {ack_msg_id}")
            return
        
        # ===== DEDUPLICATION FOR NON-CHUNK MESSAGES =====
        if msg_id and state.is_duplicate(sender, msg_id):
            logger.debug(f"⊗ Duplicate message {msg_id} from {sender}")
            return
        
        # ===== COMMAND ACK =====
        if cmd_type == MSG_TYPE_CMD_ACK:
            ack_msg_id = packet.get("ack_msg_id")
            logger.info(f"✓ Command ACK from {sender} for {ack_msg_id}")
            state.update_command_ack(ack_msg_id)
            state.update_linux_command_ack(ack_msg_id)
            return
        
        # ===== COMMAND STATUS =====
        elif cmd_type == MSG_TYPE_CMD_STATUS:
            # CRITICAL FIX: Mark data reception for half-duplex coordination
            if scheduler:
                scheduler.tx_queue.mark_reception('data')
            
            command_id = packet.get("command_id")
            script = packet.get("script")
            command_text = packet.get("command")
            exit_code = packet.get("exit_code", -1)
            feedback_type = packet.get("feedback_type", "unknown")
            message_text = packet.get("message", "")
            
            if script:
                logger.info(f"📊 Command status from {sender}: {script} - {feedback_type}")
                
                if feedback_type == "error":
                    status = "FAILED"
                elif feedback_type in ["result", "status"]:
                    status = "COMPLETED"
                else:
                    status = feedback_type.upper()
                
                state.update_command_status(command_id, script, status, exit_code)
            elif command_text:
                logger.info(f"🖥️ Linux command status from {sender}: {feedback_type}")
                state.update_linux_command_status(command_id, exit_code, feedback_type, message_text)
            
            # CRITICAL FIX: Save complete command status information
            status_data = {
                "command_id": command_id,
                "sender": sender,
                "script": script,
                "command": command_text,
                "exit_code": exit_code,
                "feedback_type": feedback_type,
                "message": message_text,
                "timestamp": packet.get("timestamp")
            }
            from logic import save_received_data
            # Save command status with all fields
            save_received_data(status_data, sender, "command_status", state)
        
        # ===== DATA PACKET =====
        elif cmd_type == MSG_TYPE_DATA:
            # CRITICAL FIX: Mark data reception for half-duplex coordination
            if scheduler:
                scheduler.tx_queue.mark_reception('data')
            
            logger.info(f"📥 Data from {sender}")
            
            # Small delay before sending ACK
            time.sleep(0.2)
            
            # FIXED: Use transmission lock for ACK
            with state.transmission_lock:
                ack = {
                    "type": MSG_TYPE_ACK,
                    "to": sender,
                    "from": CODENAME,
                    "ack_msg_id": msg_id,
                    "timestamp": time.time()
                }
                success, ack_id = lora_controller.send_packet(ack)
                if success:
                    logger.debug(f"📨 Sent ACK for {msg_id}")
                else:
                    logger.error(f"[X] Failed to send ACK for {msg_id}")
            
            # FIXED: Check payload for fish detection data
            payload = packet.get("payload", packet)
            
            # Determine the actual data type by inspecting payload
            actual_data_type = "data"
            if isinstance(payload, dict):
                payload_str = json.dumps(payload).lower()
                # Check for fish detection patterns
                if ("species" in payload_str and "detected" in payload_str) or \
                   "fish_species" in payload_str or \
                   "yolo" in payload_str or \
                   "detection_results" in payload_str:
                    actual_data_type = "fish_detection"
                    logger.info(f"🐟 Detected fish detection data in payload from {sender}")
                # Check for capture command result patterns
                elif "capture" in payload_str:
                    # Could be a capture result that contains fish data
                    if "fish" in payload_str or "species" in payload_str:
                        actual_data_type = "fish_detection"
                        logger.info(f"🐟 Detected fish detection from capture in payload from {sender}")
            
            from logic import save_received_data
            save_received_data(payload, sender, actual_data_type, state)
        
        # ===== ALIVE PING =====
        elif cmd_type == MSG_TYPE_ALIVE:
            logger.info(f"💓 Alive ping from {sender}")
        
        # ===== ALERT =====
        elif cmd_type == MSG_TYPE_ALERT:
            alert_msg = packet.get("message", "")
            logger.warning(f"🚨 ALERT from {sender}: {alert_msg}")
        
        # ===== BATTERY DATA =====
        elif cmd_type == MSG_TYPE_BATTERY:
            # CRITICAL FIX: Mark data reception for half-duplex coordination
            if scheduler:
                scheduler.tx_queue.mark_reception('data')
            
            logger.info(f"🔋 Battery data from {sender}")
            from logic import save_received_data
            save_received_data(packet, sender, "battery", state)
        
        # ===== GPS DATA =====
        elif cmd_type == MSG_TYPE_GPS or cmd_type == "gps":
            # CRITICAL FIX: Mark data reception for half-duplex coordination
            if scheduler:
                scheduler.tx_queue.mark_reception('data')
            
            logger.info(f"📍 GPS data from {sender}")
            from logic import save_received_data
            save_received_data(packet, sender, "gps", state)
        
    except json.JSONDecodeError as e:
        logger.error(f"[X] JSON parse error: {e}")
    except Exception as e:
        logger.error(f"[X] Message processing error: {e}")
        import traceback
        logger.error(traceback.format_exc())

def reassemble_chunks(state: NetworkState, sender: str, 
                     packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Reassemble chunked packets into original JSON object.
    FIXED version with proper validation
    """
    seq = packet.get("seq")
    total = packet.get("total")
    parent_id = packet.get("parent_id")
    checksum = packet.get("checksum")
    compressed = packet.get("compressed", False)
    is_b64 = packet.get("b64", True)
    data = packet.get("data")
    
    # CRITICAL FIX #2: Validate ALL required fields
    if None in (seq, total, parent_id, data, checksum):
        logger.error(f"[X] Invalid chunk packet from {sender}: missing fields")
        return None
    
    # CRITICAL FIX #3: Type validation to prevent crashes
    if not isinstance(seq, int) or not isinstance(total, int):
        logger.error(f"[X] Invalid chunk fields from {sender}: seq={seq}, total={total}")
        return None
    
    if total <= 0:
        logger.error(f"[X] Invalid chunk total={total} from {sender}")
        return None
    
    if seq < 0 or seq >= total:
        logger.error(f"[X] Invalid chunk index {seq}/{total} from {sender}")
        return None
    
    key = f"{sender}_{parent_id}"
    
    with state.chunk_lock:
        # Initialize buffer if first chunk
        if key not in state.chunk_buffer:
            state.chunk_buffer[key] = {
                "chunks": {},
                "checksum": checksum,
                "total": total,
                "compressed": compressed,
                "b64": is_b64,
                "last_seen": time.time(),
                "sender": sender
            }
        
        buffer = state.chunk_buffer[key]
        buffer["last_seen"] = time.time()
        
        # CRITICAL FIX #4: Decode Base64 with error handling
        try:
            import base64
            if is_b64:
                data_bytes = base64.b64decode(data)
            else:
                data_bytes = data if isinstance(data, bytes) else data.encode()
        except Exception as e:
            logger.error(f"[X] Base64 decode error for chunk {seq} from {sender}: {e}")
            # Don't delete buffer - other chunks might arrive
            return None
        
        # Store chunk
        buffer["chunks"][seq] = data_bytes
        
        # Check if complete - ALL chunks must be present
        if len(buffer["chunks"]) < total:
            logger.info(f"⏳ Chunk {seq+1}/{total} from {sender} (have {len(buffer['chunks'])}/{total})")
            return None
        
        # CRITICAL FIX #5: Verify ALL chunk indices are present before assembling
        missing_chunks = [i for i in range(total) if i not in buffer["chunks"]]
        if missing_chunks:
            logger.error(f"[X] Missing chunks {missing_chunks} from {sender} (have {len(buffer['chunks'])}/{total})")
            logger.error(f"   Present chunks: {sorted(buffer['chunks'].keys())}")
            # Don't delete buffer yet - chunks might still arrive
            return None
        
        # Safe reassembly - all chunks confirmed present
        try:
            full_bytes = b''.join(buffer["chunks"][i] for i in range(total))
        except KeyError as e:
            logger.error(f"[X] Missing chunk {e} from {sender} during assembly")
            del state.chunk_buffer[key]
            return None
        
        # Verify checksum (MD5, first 8 chars like BUOY)
        import hashlib
        actual_checksum = hashlib.md5(full_bytes).hexdigest()[:8]
        if actual_checksum != checksum:
            logger.error(
                f"[X] Checksum mismatch from {sender}: "
                f"expected {checksum}, got {actual_checksum}"
            )
            del state.chunk_buffer[key]
            return None
        
        # Decode CBOR+zlib or plain JSON
        try:
            if compressed:
                import cbor2
                import zlib
                json_obj = cbor2.loads(zlib.decompress(full_bytes))
            else:
                json_obj = json.loads(full_bytes.decode())
        except Exception as e:
            logger.error(f"[X] Decode error from {sender}: {e}")
            del state.chunk_buffer[key]
            return None
        
        # Success - cleanup and return
        del state.chunk_buffer[key]
        state.stats["chunks_reassembled"] += 1
        logger.info(f"✓ Reassembled {total} chunks from {sender} ({len(full_bytes)} bytes)")
        
        # Handle both dict and list payloads
        # If the reassembled JSON is a list, wrap it in a dict with a "payload" key
        if isinstance(json_obj, list):
            logger.info(f"✓ Reassembled complete transmission from {sender}")
            return {
                "type": "reassembled_data",
                "from": sender,
                "payload": json_obj,
                "timestamp": time.time()
            }
        
        return json_obj


def send_discovery_ping(lora_controller, state: Optional[NetworkState] = None):
    """
    Send discovery ping to all nodes
    FIXED: Enforces TX/RX mode switching to prevent send timeouts
    FIXED: Handles None state gracefully
    """
    if state:
        if state.is_receiving_chunks():
            logger.debug("⏸ Skipping discovery ping - receiving chunks")
            return

        if state.transmission_lock.locked():
            logger.debug("⏸ Skipping discovery ping - transmission lock active")
            return

    ping = {
        "type": MSG_TYPE_PING,
        "target": "ALL",
        "to": "ALL",
        "from": CODENAME,
        "timestamp": time.time()
    }

    # Use transmission lock if state is available, otherwise proceed without it
    lock_context = state.transmission_lock if state else dummy_context()
    
    with lock_context:
        # ---- CRITICAL FIX ----
        if not lora_controller.set_tx_mode():
            logger.error("[X] Discovery ping aborted - TX mode failed")
            return

        success, _ = lora_controller.send_packet(ping)

        # Always return to RX
        lora_controller.set_rx_mode()

        if success:
            logger.info("📡 Discovery ping sent to all nodes")
            state.stats["packets_sent"] += 1
        else:
            logger.error("[X] Discovery ping failed")

def send_command_to_buoy(state: NetworkState, lora_controller, target: str, 
                        scripts: List[str], args_dict: Dict[str, List[str]]) -> str:
    """
    Send command to BUOY node
    FIXED: Uses transmission lock to prevent interference
    FIXED: Properly switches to TX mode before sending
    """
    # For single script, send as string; for multiple, send as list
    if len(scripts) == 1:
        script_field = scripts[0]
    else:
        script_field = scripts
    
    command_packet = {
        "type": MSG_TYPE_COMMAND,
        "to": target,
        "from": CODENAME,
        "script": script_field,
        "args": args_dict,
        "timestamp": time.time()
    }
    
    # Use transmission lock
    with state.transmission_lock:
        # Switch to TX mode before sending
        if not lora_controller.set_tx_mode():
            logger.error(f"[X] Failed to set TX mode for command to {target}")
            return ""
        
        success, command_id = lora_controller.send_packet(command_packet)
        
        # Always return to RX mode
        lora_controller.set_rx_mode()
    
    if success:
        state.track_command(command_id, target, scripts)
        state.stats["packets_sent"] += 1
        logger.info(f"📤 Command {command_id} sent to {target}: {scripts}")
        return command_id
    else:
        logger.error(f"[X] Failed to send command to {target}")
        return ""


def send_linux_command_to_buoy(state: NetworkState, lora_controller, 
                               target: str, command: str) -> str:
    """
    Send Linux command to BUOY node
    FIXED: Uses transmission lock to prevent interference
    FIXED: Properly switches to TX mode before sending
    """
    linux_cmd_packet = {
        "type": "linux_cmd",  # Match BUOY's MSG_TYPE_LINUX_CMD
        "to": target,
        "from": CODENAME,
        "command": command,
        "timestamp": time.time()
    }
    
    # Use transmission lock
    with state.transmission_lock:
        # Switch to TX mode before sending
        if not lora_controller.set_tx_mode():
            logger.error(f"[X] Failed to set TX mode for Linux command to {target}")
            return ""
        
        success, command_id = lora_controller.send_packet(linux_cmd_packet)
        
        # Always return to RX mode
        lora_controller.set_rx_mode()
    
    if success:
        state.track_linux_command(command_id, target, command)
        state.stats["packets_sent"] += 1
        logger.info(f"🖥️ Linux command {command_id} sent to {target}: {command}")
        return command_id
    else:
        logger.error(f"[X] Failed to send Linux command to {target}")
        return ""