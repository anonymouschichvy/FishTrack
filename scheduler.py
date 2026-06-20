#!/usr/bin/env python3
"""
BASE Station Command Scheduler - HALF-DUPLEX FIX
"""

import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from queue import Queue, PriorityQueue, Empty
from config import *

logger = logging.getLogger("LoRaController")


class TransmissionQueue:
    """
    CRITICAL FIX: Half-duplex aware transmission queue
    Waits for chunk/data reception to complete before transmitting
    """
    
    # Priority levels
    PRIORITY_MANUAL = 0      # Manual commands have highest priority
    PRIORITY_SCHEDULED = 1   # Scheduled commands
    PRIORITY_DISCOVERY = 2   # Discovery pings have lowest priority
    
    # Reception monitoring thresholds
    CHUNK_WAIT_TIME = 3.0    # Wait 3 seconds after last chunk
    DATA_WAIT_TIME = 1.0     # Wait 1 second after last data packet
    MAX_WAIT_TIME = 30.0     # Maximum time to wait for reception to clear
    CHECK_INTERVAL = 0.5     # Check reception status every 500ms
    
    def __init__(self, network_state):
        # Use PriorityQueue to allow manual commands to jump ahead
        self.queue = PriorityQueue()
        self.lock = threading.Lock()
        self.active_transmission = None  # Currently transmitting command info
        self.transmission_start_time = None
        self.command_counter = 0  # For FIFO within same priority
        
        # CRITICAL FIX: Reference to network state for reception monitoring
        self.network_state = network_state
        
        # Reception tracking
        self.last_reception_time = 0
        self.reception_type = None  # 'chunk', 'data', or None
        
    def mark_reception(self, reception_type: str):
        """
        Mark that we just received data/chunk
        CRITICAL: This is called by process_message when data is received
        """
        with self.lock:
            self.last_reception_time = time.time()
            self.reception_type = reception_type
            logger.debug(f"[HALF-DUPLEX] Marked {reception_type} reception at {self.last_reception_time}")
    
    def is_channel_clear(self) -> tuple[bool, str]:
        """
        Check if channel is clear for transmission
        CRITICAL FIX: Half-duplex coordination
        
        Returns: (is_clear, reason)
        """
        current_time = time.time()
        
        with self.lock:
            # Check if actively receiving chunks from network state
            if self.network_state and self.network_state.is_receiving_chunks():
                time_since_last = current_time - self.last_reception_time
                return False, f"Receiving chunks (last: {time_since_last:.1f}s ago)"
            
            # Check recent reception activity
            if self.last_reception_time > 0:
                time_since_reception = current_time - self.last_reception_time
                
                # Different wait times for different reception types
                if self.reception_type == 'chunk':
                    wait_time = self.CHUNK_WAIT_TIME
                    if time_since_reception < wait_time:
                        return False, f"Chunk received {time_since_reception:.1f}s ago (waiting {wait_time}s)"
                elif self.reception_type == 'data':
                    wait_time = self.DATA_WAIT_TIME
                    if time_since_reception < wait_time:
                        return False, f"Data received {time_since_reception:.1f}s ago (waiting {wait_time}s)"
            
            # Check if transmission lock is held (another command transmitting)
            if self.network_state and self.network_state.transmission_lock.locked():
                return False, "Another transmission in progress"
        
        return True, "Clear"
    
    def wait_for_clear_channel(self, timeout: float = None) -> bool:
        """
        Wait for channel to be clear before transmitting
        CRITICAL FIX: Implements half-duplex coordination
        
        Returns: True if channel cleared, False if timeout
        """
        if timeout is None:
            timeout = self.MAX_WAIT_TIME
        
        start_time = time.time()
        last_log_time = 0
        
        while (time.time() - start_time) < timeout:
            is_clear, reason = self.is_channel_clear()
            
            if is_clear:
                logger.debug(f"[HALF-DUPLEX] ✅ Channel clear, proceeding with transmission")
                return True
            
            # Log waiting status every 2 seconds
            current_time = time.time()
            if current_time - last_log_time > 2.0:
                elapsed = current_time - start_time
                logger.info(f"[HALF-DUPLEX] ⏳ Waiting for clear channel ({elapsed:.1f}s): {reason}")
                last_log_time = current_time
            
            # Sleep briefly before checking again
            time.sleep(self.CHECK_INTERVAL)
        
        logger.warning(f"[HALF-DUPLEX] ⚠️ Timeout waiting for clear channel after {timeout}s")
        return False
    
    def add_transmission(self, command_func, *args, priority=PRIORITY_SCHEDULED, **kwargs):
        """
        Add a transmission to the queue with priority
        Lower priority number = higher priority
        """
        with self.lock:
            self.command_counter += 1
            # Use command_counter as tiebreaker for same priority (FIFO)
            self.queue.put((priority, self.command_counter, command_func, args, kwargs))
        
        priority_name = {
            self.PRIORITY_MANUAL: "MANUAL",
            self.PRIORITY_SCHEDULED: "SCHEDULED", 
            self.PRIORITY_DISCOVERY: "DISCOVERY"
        }.get(priority, f"PRIORITY_{priority}")
        
        logger.info(f"[TX_QUEUE] Queued {priority_name}: {command_func.__name__} (queue_size={self.queue.qsize()})")
    
    def process_queue(self, lora_controller):
        """
        Process queued transmissions one at a time
        CRITICAL FIX: Half-duplex aware - waits for reception to complete
        CRITICAL FIX: Handles TX/RX mode switching before and after transmission
        """
        logger.info("[TX_QUEUE] Transmission queue processor started (HALF-DUPLEX MODE)")
        
        while True:
            try:
                # Get next command from queue (blocks with timeout)
                priority, counter, command_func, args, kwargs = self.queue.get(timeout=0.1)
                
                priority_name = {
                    self.PRIORITY_MANUAL: "MANUAL",
                    self.PRIORITY_SCHEDULED: "SCHEDULED",
                    self.PRIORITY_DISCOVERY: "DISCOVERY"
                }.get(priority, f"PRIORITY_{priority}")
                
                logger.info(f"[TX_QUEUE] Processing {priority_name}: {command_func.__name__}")
                
                # CRITICAL FIX: Wait for channel to be clear before transmitting
                logger.info(f"[HALF-DUPLEX] 🔍 Checking channel before transmission...")
                channel_clear = self.wait_for_clear_channel(timeout=self.MAX_WAIT_TIME)
                
                if not channel_clear:
                    logger.error(f"[HALF-DUPLEX] ❌ Channel not clear, skipping {command_func.__name__}")
                    self.queue.task_done()
                    continue
                
                # CRITICAL FIX: Switch to TX mode BEFORE transmission
                logger.debug(f"[TX_QUEUE] Switching to TX mode for transmission...")
                if not lora_controller.set_tx_mode():
                    logger.error(f"[TX_QUEUE] ❌ Failed to switch to TX mode, skipping {command_func.__name__}")
                    self.queue.task_done()
                    continue
                
                # CRITICAL FIX: Only lock during the actual transmission
                with self.lock:
                    self.active_transmission = {
                        "function": command_func.__name__,
                        "priority": priority_name,
                        "started_at": time.time()
                    }
                
                try:
                    logger.info(f"[TX_QUEUE] 📤 Executing {priority_name}: {command_func.__name__}")
                    
                    # Execute the command (this may send and wait for response)
                    result = command_func(*args, **kwargs)
                    
                    logger.info(f"[TX_QUEUE] ✅ Completed {priority_name}: {command_func.__name__}")
                    
                except Exception as e:
                    logger.error(f"[TX_QUEUE] ❌ Execution error in {command_func.__name__}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                
                finally:
                    # CRITICAL FIX: Switch back to RX mode AFTER transmission
                    logger.debug(f"[TX_QUEUE] Switching back to RX mode...")
                    lora_controller.set_rx_mode()
                    
                    # Clear active transmission status
                    with self.lock:
                        self.active_transmission = None
                    
                    # Mark task as done
                    self.queue.task_done()
                    
                    # Small delay between transmissions to prevent LoRa overflow
                    time.sleep(0.5)
                        
            except Empty:
                # No commands in queue, sleep briefly
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"[TX_QUEUE] Queue processing error: {e}")
                with self.lock:
                    self.active_transmission = None
                time.sleep(1)
    
    def get_queue_size(self):
        """Get current queue size"""
        return self.queue.qsize()
    
    def is_transmitting(self):
        """Check if currently transmitting"""
        with self.lock:
            return self.active_transmission is not None
    
    def get_active_transmission(self):
        """Get info about currently transmitting command"""
        with self.lock:
            if self.active_transmission:
                info = self.active_transmission.copy()
                info['duration'] = time.time() - info['started_at']
                return info
            return None
    
    def get_reception_status(self):
        """Get current reception status"""
        with self.lock:
            if self.last_reception_time > 0:
                time_since = time.time() - self.last_reception_time
                return {
                    "last_reception": self.last_reception_time,
                    "time_since": time_since,
                    "type": self.reception_type,
                    "is_receiving": self.network_state.is_receiving_chunks() if self.network_state else False
                }
            return None


class CommandScheduler:
    """
    Manages scheduled commands to BUOY nodes
    CRITICAL FIX: Half-duplex aware scheduling
    """
    
    def __init__(self, state, lora_controller):
        self.state = state
        self.lora = lora_controller
        self.schedules_file = SCHEDULED_COMMANDS_FILE
        self.schedules = []
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # CRITICAL FIX: Half-duplex aware transmission queue
        self.tx_queue = TransmissionQueue(state)
        self.tx_thread = None
        
        # Track executing schedules to prevent deletion during execution
        self.executing_schedules = set()
        
        # Track paused schedules (paused by user or by system)
        self.paused_schedules = set()
        
        self.load_schedules()
    
    def load_schedules(self):
        """Load schedules from file"""
        try:
            if self.schedules_file.exists():
                with open(self.schedules_file, 'r') as f:
                    self.schedules = json.load(f)
                logger.info(f"[SCHEDULER] Loaded {len(self.schedules)} scheduled commands")
            else:
                self.schedules = []
                logger.info("[SCHEDULER] No existing schedules found, starting fresh")
        except Exception as e:
            logger.error(f"[SCHEDULER] Failed to load schedules: {e}")
            self.schedules = []
    
    def save_schedules(self):
        """
        Save schedules to file with atomic write
        CRITICAL FIX: Uses temp file to prevent corruption
        """
        try:
            # Ensure parent directory exists
            self.schedules_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Atomic write using temp file
            temp_file = self.schedules_file.with_suffix('.tmp')
            
            # Write to temp file first
            with open(temp_file, 'w') as f:
                json.dump(self.schedules, f, indent=2)
            
            # Verify the temp file was written correctly
            with open(temp_file, 'r') as f:
                json.load(f)  # Will raise exception if invalid JSON
            
            # Atomic rename (overwrites original safely)
            temp_file.replace(self.schedules_file)
            
            logger.debug(f"[SCHEDULER] Schedules saved successfully ({len(self.schedules)} schedules)")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"[SCHEDULER] JSON validation failed: {e}")
            if temp_file.exists():
                temp_file.unlink()
            return False
            
        except Exception as e:
            logger.error(f"[SCHEDULER] Failed to save schedules: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def add_schedule(self, schedule: Dict[str, Any]) -> str:
        """Add a new scheduled command"""
        # Validate required fields
        required_fields = ['name', 'target', 'scripts', 'frequency']
        for field in required_fields:
            if field not in schedule:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate target is in active list
        if schedule['target'] not in ACTIVE_BUOY_LIST:
            raise ValueError(f"Target {schedule['target']} not in active BUOY list")
        
        with self.lock:
            # Generate schedule ID
            schedule_id = f"sched_{int(time.time())}_{len(self.schedules)}"
            
            current_time = time.time()
            schedule.update({
                "id": schedule_id,
                "created_at": current_time,
                "enabled": True,
                "last_run": None,
                "run_count": 0
            })
            
            # Calculate next_run after setting all fields
            schedule['next_run'] = self._calculate_next_run(schedule, current_time)
            
            self.schedules.append(schedule)
            success = self.save_schedules()
            
            if success:
                logger.info(f"[SCHEDULER] ✅ Added schedule {schedule_id}: {schedule['name']}")
                return schedule_id
            else:
                # Rollback if save failed
                self.schedules.pop()
                raise Exception("Failed to save schedule to disk")
    
    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a scheduled command"""
        logger.info(f"[SCHEDULER] Attempting to remove schedule: {schedule_id}")
        
        with self.lock:
            # Check if schedule is currently executing
            if schedule_id in self.executing_schedules:
                logger.warning(f"[SCHEDULER] ❌ Cannot delete {schedule_id} - currently executing")
                return False
            
            # Find the schedule
            schedule_to_remove = None
            for s in self.schedules:
                if s['id'] == schedule_id:
                    schedule_to_remove = s
                    break
            
            if not schedule_to_remove:
                logger.warning(f"[SCHEDULER] ❌ Schedule {schedule_id} not found in list")
                return False
            
            # Keep a backup
            original_count = len(self.schedules)
            original_schedules = self.schedules.copy()
            
            # Remove the schedule
            self.schedules = [s for s in self.schedules if s['id'] != schedule_id]
            
            # Also remove from paused set if present
            self.paused_schedules.discard(schedule_id)
            
            logger.info(f"[SCHEDULER] Removed from memory: {schedule_to_remove['name']}")
            logger.info(f"[SCHEDULER] Schedule count: {original_count} -> {len(self.schedules)}")
            
            # Save to disk
            success = self.save_schedules()
            
            if success:
                logger.info(f"[SCHEDULER] ✅ Successfully removed schedule {schedule_id} from disk")
                return True
            else:
                # Rollback if save failed
                self.schedules = original_schedules
                logger.error(f"[SCHEDULER] ❌ Failed to save after removing {schedule_id}, rolled back")
                return False
    
    def update_schedule(self, schedule_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing schedule"""
        with self.lock:
            # Check if schedule is currently executing
            if schedule_id in self.executing_schedules:
                logger.warning(f"[SCHEDULER] Cannot update {schedule_id} - currently executing")
                return False
            
            for schedule in self.schedules:
                if schedule['id'] == schedule_id:
                    # Store old values for rollback
                    old_values = schedule.copy()
                    
                    try:
                        schedule.update(updates)
                        # Recalculate next run time
                        schedule['next_run'] = self._calculate_next_run(schedule, time.time())
                        
                        success = self.save_schedules()
                        if success:
                            logger.info(f"[SCHEDULER] ✅ Updated schedule {schedule_id}")
                            return True
                        else:
                            # Rollback on save failure
                            schedule.update(old_values)
                            logger.error(f"[SCHEDULER] Failed to save updates, rolled back")
                            return False
                    except Exception as e:
                        # Rollback on error
                        schedule.update(old_values)
                        logger.error(f"[SCHEDULER] Update failed: {e}, rolled back")
                        return False
            
            logger.warning(f"[SCHEDULER] Schedule {schedule_id} not found")
            return False
    
    def toggle_schedule(self, schedule_id: str) -> bool:
        """Enable/disable a schedule"""
        logger.info(f"[SCHEDULER] Attempting to toggle schedule: {schedule_id}")
        
        with self.lock:
            schedule_found = None
            for schedule in self.schedules:
                if schedule['id'] == schedule_id:
                    schedule_found = schedule
                    break
            
            if not schedule_found:
                logger.warning(f"[SCHEDULER] ❌ Schedule {schedule_id} not found")
                return False
            
            old_enabled = schedule_found.get('enabled', True)
            new_enabled = not old_enabled
            
            logger.info(f"[SCHEDULER] Toggling {schedule_found['name']}: {old_enabled} -> {new_enabled}")
            
            schedule_found['enabled'] = new_enabled
            
            # If disabling, set next_run to None to prevent execution
            if not new_enabled:
                schedule_found['next_run'] = None
                logger.info(f"[SCHEDULER] Disabled schedule {schedule_id}, cleared next_run")
            else:
                # If enabling, recalculate next_run
                schedule_found['next_run'] = self._calculate_next_run(schedule_found, time.time())
                next_time = self._format_time(schedule_found['next_run'])
                logger.info(f"[SCHEDULER] Enabled schedule {schedule_id}, next_run: {next_time}")
            
            # Save to disk
            success = self.save_schedules()
            
            if success:
                status = "enabled" if new_enabled else "disabled"
                logger.info(f"[SCHEDULER] ✅ Schedule {schedule_id} successfully {status}")
                return True
            else:
                # Rollback on save failure
                schedule_found['enabled'] = old_enabled
                if old_enabled:
                    schedule_found['next_run'] = self._calculate_next_run(schedule_found, time.time())
                else:
                    schedule_found['next_run'] = None
                logger.error(f"[SCHEDULER] ❌ Failed to save toggle, rolled back")
                return False
    
    def get_schedules(self) -> List[Dict[str, Any]]:
        """Get all schedules"""
        with self.lock:
            return [self._format_schedule(s) for s in self.schedules]
    
    def _format_schedule(self, schedule: Dict[str, Any]) -> Dict[str, Any]:
        """Format schedule for display"""
        return {
            "id": schedule['id'],
            "name": schedule['name'],
            "target": schedule['target'],
            "scripts": schedule['scripts'],
            "args": schedule.get('args', {}),
            "frequency": schedule['frequency'],
            "time_of_day": schedule.get('time_of_day'),
            "days_of_week": schedule.get('days_of_week'),
            "interval_minutes": schedule.get('interval_minutes'),
            "enabled": schedule.get('enabled', True),
            "last_run": self._format_time(schedule.get('last_run')),
            "next_run": self._format_time(schedule.get('next_run')),
            "run_count": schedule.get('run_count', 0),
            "created_at": self._format_time(schedule.get('created_at')),
            "is_executing": schedule['id'] in self.executing_schedules,
            "is_paused": schedule['id'] in self.paused_schedules
        }
    
    def _format_time(self, timestamp: Optional[float]) -> Optional[str]:
        """Format Unix timestamp to readable string"""
        if timestamp:
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        return None
    
    def _calculate_next_run(self, schedule: Dict[str, Any], current_time: float) -> Optional[float]:
        """Calculate next run time based on frequency"""
        # Return None if disabled
        if not schedule.get('enabled', True):
            return None
        
        now = datetime.fromtimestamp(current_time)
        frequency = schedule.get('frequency', 'daily')
        
        if frequency == 'once':
            time_of_day = schedule.get('time_of_day', '00:00')
            run_time = datetime.strptime(time_of_day, "%H:%M").time()
            next_run = datetime.combine(now.date(), run_time)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run.timestamp()
        
        elif frequency == 'hourly':
            time_of_day = schedule.get('time_of_day', '00:00')
            minutes = int(time_of_day.split(':')[1])
            next_run = now.replace(minute=minutes, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(hours=1)
            return next_run.timestamp()
        
        elif frequency == 'daily':
            time_of_day = schedule.get('time_of_day', '00:00')
            run_time = datetime.strptime(time_of_day, "%H:%M").time()
            next_run = datetime.combine(now.date(), run_time)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run.timestamp()
        
        elif frequency == 'weekly':
            time_of_day = schedule.get('time_of_day', '00:00')
            run_time = datetime.strptime(time_of_day, "%H:%M").time()
            days_of_week = schedule.get('days_of_week', [0])
            
            # Check today first
            if now.weekday() in days_of_week:
                next_run = datetime.combine(now.date(), run_time)
                if next_run > now:
                    return next_run.timestamp()
            
            # Find next occurrence in the next 7 days
            for i in range(1, 8):
                check_date = now + timedelta(days=i)
                if check_date.weekday() in days_of_week:
                    next_run = datetime.combine(check_date.date(), run_time)
                    return next_run.timestamp()
            
            # Fallback
            next_run = datetime.combine(now.date() + timedelta(days=7), run_time)
            return next_run.timestamp()
        
        elif frequency == 'interval':
            interval_minutes = schedule.get('interval_minutes', 60)
            last_run = schedule.get('last_run')
            
            if last_run is None:
                # First run: schedule based on current time
                next_run = now + timedelta(minutes=interval_minutes)
            else:
                # Subsequent runs: schedule from last run
                next_run = datetime.fromtimestamp(last_run) + timedelta(minutes=interval_minutes)
                # If we're behind schedule, run soon
                if next_run <= now:
                    next_run = now + timedelta(seconds=30)
            
            return next_run.timestamp()
        
        else:
            logger.warning(f"[SCHEDULER] Unknown frequency type: {frequency}, defaulting to 1 hour")
            return (now + timedelta(hours=1)).timestamp()
    
    def _should_run(self, schedule: Dict[str, Any], current_time: float) -> bool:
        """Check if schedule should run now"""
        # Check if enabled
        if not schedule.get('enabled', True):
            return False
        
        # Check if paused
        if schedule['id'] in self.paused_schedules:
            return False
        
        # Check if already executing
        if schedule['id'] in self.executing_schedules:
            return False
        
        # Check next_run time
        next_run = schedule.get('next_run')
        if not next_run:
            return False
        
        return current_time >= next_run
    
    def _execute_schedule(self, schedule: Dict[str, Any]):
        """
        Execute a scheduled command
        CRITICAL FIX: Uses priority queue with half-duplex coordination
        """
        schedule_id = schedule['id']
        
        try:
            # Mark as executing
            with self.lock:
                self.executing_schedules.add(schedule_id)
            
            target = schedule['target']
            scripts = schedule['scripts']
            args_dict = schedule.get('args', {})
            
            logger.info(f"[SCHEDULER] ⏰ Executing scheduled: {schedule['name']} -> {target}")
            
            try:
                from logic import send_command_to_buoy
            except ImportError as e:
                logger.error(f"[SCHEDULER] Failed to import send_command_to_buoy: {e}")
                return
            
            # CRITICAL FIX: Queue with SCHEDULED priority (manual commands will jump ahead)
            # Half-duplex coordination happens in process_queue
            self.tx_queue.add_transmission(
                send_command_to_buoy,
                self.state,
                self.lora,
                target,
                scripts,
                args_dict,
                priority=TransmissionQueue.PRIORITY_SCHEDULED
            )
            
            # Update schedule with lock
            current_time = time.time()
            with self.lock:
                # Check if schedule still exists (not deleted during execution)
                schedule_found = False
                for s in self.schedules:
                    if s['id'] == schedule_id:
                        schedule_found = True
                        s['last_run'] = current_time
                        s['run_count'] = s.get('run_count', 0) + 1
                        
                        # Calculate next run or disable
                        if schedule['frequency'] == 'once':
                            s['enabled'] = False
                            s['next_run'] = None
                            logger.info(f"[SCHEDULER] One-time schedule {s['id']} completed and disabled")
                        else:
                            s['next_run'] = self._calculate_next_run(s, current_time)
                            next_time = self._format_time(s['next_run'])
                            logger.info(f"[SCHEDULER] Next run scheduled for: {next_time}")
                        
                        self.save_schedules()
                        break
                
                if not schedule_found:
                    logger.warning(f"[SCHEDULER] Schedule {schedule_id} was deleted during execution")
            
            logger.info(f"[SCHEDULER] ✅ Command queued successfully")
            
        except Exception as e:
            logger.error(f"[SCHEDULER] Failed to execute scheduled command: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        finally:
            # Always remove from executing set
            with self.lock:
                self.executing_schedules.discard(schedule_id)
    
    def start(self):
        """Start the scheduler thread"""
        if self.running:
            logger.warning("[SCHEDULER] Already running")
            return
        
        self.running = True
        
        # Start transmission queue processor
        self.tx_thread = threading.Thread(
            target=self.tx_queue.process_queue,
            args=(self.lora,),
            daemon=True
        )
        self.tx_thread.start()
        logger.info("[SCHEDULER] ✅ Transmission queue processor started (HALF-DUPLEX MODE)")
        
        # Start scheduler loop
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        logger.info("[SCHEDULER] ✅ Scheduler loop started")
    
    def stop(self):
        """Stop the scheduler thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("[SCHEDULER] Stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        logger.info("[SCHEDULER] Main loop started")
        
        while self.running:
            try:
                current_time = time.time()
                
                # Get schedules to run (with lock)
                with self.lock:
                    schedules_to_run = [
                        s.copy() for s in self.schedules 
                        if self._should_run(s, current_time)
                    ]
                
                # Execute due schedules (outside lock to prevent deadlock)
                for schedule in schedules_to_run:
                    self._execute_schedule(schedule)
                
                # Sleep for 30 seconds before next check
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"[SCHEDULER] Loop error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(60)
    
    def get_next_scheduled(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get next scheduled commands"""
        with self.lock:
            enabled_schedules = [
                s for s in self.schedules 
                if s.get('enabled', True) and s.get('next_run') is not None
            ]
            enabled_schedules.sort(key=lambda x: x.get('next_run', float('inf')))
            return [self._format_schedule(s) for s in enabled_schedules[:limit]]
    
    def queue_manual_command(self, command_func, *args, **kwargs):
        """
        CRITICAL FIX: Queue manual commands with HIGH priority
        They will jump ahead of scheduled commands in the queue
        Half-duplex coordination happens automatically in process_queue
        """
        self.tx_queue.add_transmission(
            command_func, 
            *args, 
            priority=TransmissionQueue.PRIORITY_MANUAL,
            **kwargs
        )
        logger.info("[SCHEDULER] 🚨 Manual command queued with HIGH priority")
    
    def queue_discovery_ping(self, command_func, *args, **kwargs):
        """
        Queue discovery ping with LOW priority
        Will wait for both manual and scheduled commands
        Half-duplex coordination happens automatically in process_queue
        """
        self.tx_queue.add_transmission(
            command_func,
            *args,
            priority=TransmissionQueue.PRIORITY_DISCOVERY,
            **kwargs
        )
        logger.debug("[SCHEDULER] Discovery ping queued with LOW priority")
    
    def get_transmission_status(self):
        """Get transmission queue status"""
        active = self.tx_queue.get_active_transmission()
        reception = self.tx_queue.get_reception_status()
        channel_clear, reason = self.tx_queue.is_channel_clear()
        
        return {
            "queue_size": self.tx_queue.get_queue_size(),
            "is_transmitting": self.tx_queue.is_transmitting(),
            "active_transmission": active,
            "executing_schedules": list(self.executing_schedules),
            "paused_schedules": list(self.paused_schedules),
            "reception_status": reception,
            "channel_clear": channel_clear,
            "channel_status": reason
        }