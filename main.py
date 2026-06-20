#!/usr/bin/env python3
"""
BASE Station Main Entry Point
LoRa Mesh Network Control Center
FIXED: Proper scheduler initialization and transmission queue coordination
"""

import sys
import time
import logging
import threading
import argparse
import io
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Fix Windows console encoding BEFORE any other imports
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import config
from config import *
from hardware import LoRaController
from logic import NetworkState, process_message, send_discovery_ping, cleanup_chunk_buffer
from scheduler import CommandScheduler
import server


# Setup logging
def setup_logging():
    """Setup rotating file logger"""
    log = logging.getLogger("LoRaController")
    log.setLevel(logging.INFO)
    
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'  # Important for emoji support
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    log.addHandler(handler)
    
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(message)s'))
    log.addHandler(console)
    
    return log


def maintenance_loop(state: NetworkState, lora_controller, scheduler):
    """
    Background maintenance tasks
    FIXED: Uses transmission queue for all transmissions to prevent race conditions
    RACE FIX: Discovery pings use LOW priority to not interfere with manual/scheduled commands
    """
    last_discovery = 0
    last_neighbor_cleanup = 0
    last_chunk_cleanup = 0
    last_table_print = 0
    last_stats_print = 0
    
    while True:
        try:
            current_time = time.time()
            
            # Discovery pings - RACE FIX: Use LOW priority queue method
            if current_time - last_discovery > DISCOVERY_INTERVAL:
                scheduler.queue_discovery_ping(
                    send_discovery_ping,
                    lora_controller,
                    state
                )
                last_discovery = current_time
            
            # Neighbor cleanup
            if current_time - last_neighbor_cleanup > CLEANUP_INTERVAL:
                state.cleanup_stale_neighbors()
                last_neighbor_cleanup = current_time
            
            # Chunk buffer cleanup
            if current_time - last_chunk_cleanup > 60:
                cleanup_chunk_buffer(state)
                last_chunk_cleanup = current_time
            
            # Print neighbor table
            if current_time - last_table_print > TABLE_PRINT_INTERVAL:
                print_neighbor_table(state)
                last_table_print = current_time
            
            # Print statistics
            if current_time - last_stats_print > STATS_PRINT_INTERVAL:
                print_statistics(state)
                last_stats_print = current_time
            
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"[X] Maintenance error: {e}")
            time.sleep(10)


def print_neighbor_table(state: NetworkState):
    """Display current neighbor information"""
    summary = state.get_neighbor_summary()
    
    if summary["total"] == 0:
        logger.info("[i] Neighbor Table: (empty)")
        return
    
    logger.info("[i] Neighbor Table:")
    current_time = time.time()
    
    for codename, info in sorted(summary["neighbors"].items()):
        last_seen = int(current_time - info["last_seen"])
        hops = info.get('hops', '?')
        rssi = info.get('rssi', 'N/A')
        is_direct = info.get("last_direct") is not None
        direct_indicator = "[DIRECT]" if is_direct else "[RELAY]"
        
        logger.info(f"  {codename}: hops={hops}, last_seen={last_seen}s ago, "
                   f"rssi={rssi}, {direct_indicator}")
    
    logger.info(f"  Summary: {summary['total']} total "
               f"({summary['direct']} direct, {summary['relay']} relayed)")


def print_statistics(state: NetworkState):
    """Print network statistics"""
    logger.info("[i] Network Statistics:")
    logger.info(f"  Packets sent: {state.stats['packets_sent']}")
    logger.info(f"  Packets received: {state.stats['packets_received']}")
    logger.info(f"  Chunks reassembled: {state.stats['chunks_reassembled']}")
    logger.info(f"  Chunk ACKs received: {state.stats['chunk_acks_received']}")
    logger.info(f"  Duplicates dropped: {state.stats['duplicates_dropped']}")
    logger.info(f"  Commands sent: {state.stats['commands_sent']}")
    logger.info(f"  Commands completed: {state.stats['commands_completed']}")


def web_server_thread(state: NetworkState, lora_ctrl: LoRaController, cmd_scheduler):
    """Run Flask web server in separate thread"""
    server.run_server(state, lora_ctrl, cmd_scheduler)


def main():
    global logger, lora
    
    parser = argparse.ArgumentParser(description="BASE Station - LoRa Mesh Network")
    parser.add_argument("--port", default=SERIAL_PORT, help="Serial port")
    parser.add_argument("--web-port", type=int, default=WEB_PORT, help="Web server port")
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    
    logger.info("="*60)
    logger.info(f"BASE Station - {CODENAME}")
    logger.info(f"LoRa Multi-Hop Mesh Network Control Center")
    logger.info("="*60)
    
    # Initialize network state and pre-populate caches
    state = NetworkState()
    state.init_caches_from_disk()
    logger.info(f"[i] Active List: {len(ACTIVE_BUOY_LIST)} expected nodes")
    for node in ACTIVE_BUOY_LIST:
        logger.info(f"  - {node}")
    
    # Initialize LoRa controller
    lora = LoRaController(args.port)
    if not lora.connect():
        logger.error("[X] Failed to connect to LoRa module")
        sys.exit(1)
    
    # CRITICAL FIX: Initialize scheduler with correct parameter order (state, lora)
    cmd_scheduler = CommandScheduler(state, lora)
    if SCHEDULER_ENABLED:
        cmd_scheduler.start()
        logger.info("[+] Command scheduler started")
    
    # CRITICAL FIX: Start maintenance thread - Pass scheduler parameter
    maintenance_thread = threading.Thread(
        target=maintenance_loop,
        args=(state, lora, cmd_scheduler),  # FIXED: Added scheduler parameter
        daemon=True
    )
    maintenance_thread.start()
    logger.info("[+] Maintenance thread started")
    
    # Start web server thread
    web_thread = threading.Thread(
        target=web_server_thread,
        args=(state, lora, cmd_scheduler),
        daemon=True
    )
    web_thread.start()
    logger.info("[+] Web server thread started")
    
    # Main message loop
    logger.info("[*] Entering main message loop...")
    logger.info(f"[i] Dashboard available at: http://localhost:{args.web_port}")
    
    try:
        while True:
            # Receive and process messages
            msg = lora.receive_message(timeout=0.2)
            if msg:
                process_message(state, lora, msg)
            
            time.sleep(0.05)
    
    except KeyboardInterrupt:
        logger.info("\n[!] Shutting down BASE station...")
    
    except Exception as e:
        logger.error(f"[X] Fatal error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if SCHEDULER_ENABLED:
            cmd_scheduler.stop()
        lora.close()
        logger.info("[+] BASE station shutdown complete")


if __name__ == "__main__":
    main()