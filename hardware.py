#!/usr/bin/env python3
import serial
import time
import json
import threading
import logging
from typing import Optional, Tuple, Dict, Any
from config import *
from utils import generate_msg_id

logger = logging.getLogger("LoRaController")

class LoRaController:
    """
    LoRa hardware controller - HALF DUPLEX operation
    Must explicitly switch between TX and RX modes
    Pico does NOT queue messages - sends immediately
    """
    
    def __init__(self, port: str = SERIAL_PORT, baudrate: int = BAUD_RATE):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.current_mode = "RX"
        self.lock = threading.RLock()
        self.rx_buffer = ""
        self.connection_healthy = False
        self.initialized = False
        self.is_reconnecting = False
    
    def _read_line_internal(self, timeout: float = 1.0) -> Optional[str]:
        """Read a single line from Pico"""
        start_time = time.time()
        line_buffer = ""
        
        while time.time() - start_time < timeout:
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting:
                    chunk = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='replace')
                    line_buffer += chunk
                    
                    if '\n' in line_buffer:
                        line, line_buffer = line_buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            return line
            except Exception as e:
                logger.debug(f"[!] Read error: {e}")
                return None
            
            time.sleep(0.01)
        
        return None
    
    def _wait_for_response(self, expected_prefix: str, timeout: float = 2.0, 
                          skip_debug: bool = True) -> Optional[str]:
        """
        Wait for a specific response from Pico
        FIXED: Skip DEBUG messages and increase timeout for mode switches
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            line = self._read_line_internal(timeout=0.5)
            if line:
                # Skip DEBUG messages unless we're looking for them
                if skip_debug and line.startswith("DEBUG:"):
                    logger.debug(f"[PICO-DEBUG] {line}")
                    continue
                
                logger.debug(f"[PICO] {line}")
                if line.startswith(expected_prefix):
                    return line
            time.sleep(0.01)
        
        return None
    
    def _flush_buffers(self):
        """Flush serial buffers"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.05)
        except Exception as e:
            logger.debug(f"[!] Flush error: {e}")
    
    def connect(self) -> bool:
        """Connect to Pico with initialization - FIXED VERSION"""
        with self.lock:
            self.is_reconnecting = True
            attempt = 0
            
            while attempt < 5:
                try:
                    if self.ser and self.ser.is_open:
                        try:
                            self.ser.close()
                        except:
                            pass
                        time.sleep(0.5)
                    
                    logger.info(f"[>] Connecting to {self.port} (attempt {attempt + 1}/5)...")
                    self.ser = serial.Serial(
                        self.port, 
                        self.baudrate, 
                        timeout=0.1,
                        write_timeout=2.0  # CRITICAL FIX: Increased from 1.0 to 2.0 to prevent timeouts
                    )
                    
                    # CRITICAL FIX: Give Pico time to start and send initial messages
                    logger.info("[>] Waiting for Pico initialization...")
                    time.sleep(1.0)  # Initial wait
                    
                    # FIXED: Consume ALL startup messages (READY, INIT, BRIDGE_READY, etc.)
                    # This prevents them from interfering with STATUS response
                    logger.debug("[>] Consuming Pico startup messages...")
                    startup_timeout = time.time() + 4.0  # 4 seconds to collect startup
                    startup_messages = []
                    
                    while time.time() < startup_timeout:
                        if self.ser.in_waiting:
                            try:
                                chunk = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='replace')
                                if chunk:
                                    lines = chunk.strip().split('\n')
                                    for line in lines:
                                        line = line.strip()
                                        if line:
                                            startup_messages.append(line)
                                            logger.debug(f"[PICO-STARTUP] {line}")
                                            
                                            # Check for RX messages from buoy (these are NOT startup)
                                            if line.startswith("RX:"):
                                                logger.info(f"[+] Early RX message detected (buoy alive)")
                            except Exception as e:
                                logger.debug(f"[!] Startup read error: {e}")
                        time.sleep(0.05)
                    
                    # Log collected startup messages
                    if startup_messages:
                        logger.info(f"[+] Pico sent {len(startup_messages)} startup messages")
                    else:
                        logger.warning("[!] No startup messages received (Pico may have been already running)")
                    
                    # CRITICAL: Clear buffers AFTER reading all startup messages
                    # This ensures we start fresh for STATUS command
                    self._flush_buffers()
                    time.sleep(0.1)
                    
                    # Now send STATUS command with clean buffers
                    logger.debug("[>] Sending STATUS command...")
                    self.ser.write(b"STATUS\n")
                    self.ser.flush()
                    
                    self.ser.write(b"STATUS\n")
                    self.ser.flush()

                    lines = self._collect_lines(timeout=3.0)

                    logger.debug("[STATUS RAW]")
                    for l in lines:
                        logger.debug(f"  {l}")

                    mode_line = next((l for l in lines if l.startswith("MODE:")), None)

                    if mode_line:
                        self.current_mode = mode_line.split(":", 1)[1].strip()
                        logger.info(f"[+] Connected to {self.port}")
                        logger.info(f"[+] Pico mode: {self.current_mode}")
                        self.connection_healthy = True
                        self.initialized = True
                        self.is_reconnecting = False
                        return True

                    raise Exception(f"Pico not responding to STATUS - got lines: {lines}")
                    
                    if response and response.startswith("MODE:"):
                        logger.info(f"[+] Connected to {self.port}")
                        logger.info(f"[+] Pico status: {response}")
                        
                        # Parse mode
                        try:
                            self.current_mode = response.split(':')[1].strip()
                            logger.info(f"[+] Current mode: {self.current_mode}")
                        except:
                            self.current_mode = "RX"
                        
                        self.connection_healthy = True
                        self.initialized = True
                        self.is_reconnecting = False
                        return True
                    else:
                        raise Exception(f"Pico not responding to STATUS - got: {response}")
                        
                except Exception as e:
                    attempt += 1
                    logger.error(f"[X] Connection attempt {attempt}/5 failed: {e}")
                    if attempt < 5:
                        logger.info(f"[>] Retrying in 5 seconds...")
                        time.sleep(5)
            
            self.connection_healthy = False
            self.initialized = False
            self.is_reconnecting = False
            return False
    
    def reconnect(self) -> bool:
        """Reconnect to Pico"""
        logger.warning("[!] Attempting to reconnect...")
        self.connection_healthy = False
        self.initialized = False
        return self.connect()
    
    def is_connected(self) -> bool:
        """Check connection health"""
        with self.lock:
            return (self.ser is not None and 
                    self.ser.is_open and 
                    self.connection_healthy and 
                    self.initialized and
                    not self.is_reconnecting)
    
    def set_tx_mode(self) -> bool:
        """
        Switch to TX mode (HALF DUPLEX - blocks RX)
        Must be called BEFORE sending
        FIXED: Better error handling and removed duplicate command
        """
        with self.lock:
            if not self.is_connected():
                logger.error("[X] Cannot set TX mode - not connected")
                return False
                
            if self.current_mode == "TX":
                logger.debug("[+] Already in TX mode")
                return True
            
            try:
                logger.debug("[>] Switching to TX mode...")
                
                # CRITICAL FIX: Clear any pending data in buffers first
                try:
                    self._flush_buffers()
                except Exception as flush_error:
                    logger.debug(f"[!] Buffer flush warning: {flush_error}")
                
                # Send TX command with error handling
                try:
                    self.ser.write(b"TX\n")
                    self.ser.flush()
                except serial.SerialTimeoutException:
                    logger.warning("[!] Write timeout on TX command, retrying...")
                    time.sleep(0.2)
                    # Try one more time
                    try:
                        self.ser.write(b"TX\n")
                        self.ser.flush()
                    except serial.SerialTimeoutException:
                        logger.warning("[!] Write timeout persists - Pico may be busy")
                        time.sleep(0.5)

                lines = self._collect_lines(timeout=1)

                logger.debug("[TX RAW RESPONSE]")
                for l in lines:
                    logger.debug(f"  {l}")

                
                if any(l == "OK:TX" for l in lines):
                    self.current_mode = "TX"
                    logger.info("[+] ✓ TX mode active")
                    return True
                
                # CRITICAL FIX: If no OK:TX but no errors either, check if already in TX
                if not any(l.startswith("ERROR:") for l in lines):
                    # Verify mode by checking STATUS
                    logger.debug("[!] No OK:TX response, verifying mode...")
                    try:
                        self.ser.write(b"STATUS\n")
                        self.ser.flush()
                        status_lines = self._collect_lines(timeout=1.0)
                        mode_line = next((l for l in status_lines if l.startswith("MODE:")), None)
                        if mode_line and "TX" in mode_line:
                            logger.info("[+] ✓ TX mode verified via STATUS")
                            self.current_mode = "TX"
                            return True
                    except:
                        pass

                logger.error(f"[X] TX mode failed, got lines: {lines}")
                return False
                    
            except serial.SerialTimeoutException as e:
                logger.error(f"[X] TX mode write timeout: {e}")
                return False
                
            except Exception as e:
                logger.error(f"[X] TX mode error: {e}")
                return False
    
    def set_rx_mode(self) -> bool:
        """
        Switch to RX mode (HALF DUPLEX - blocks TX)
        Default mode for receiving messages
        FIXED: Better error handling and recovery from write timeouts
        """
        with self.lock:
            if not self.is_connected():
                logger.error("[X] Cannot set RX mode - not connected")
                return False
                
            if self.current_mode == "RX":
                logger.debug("[+] Already in RX mode")
                return True
            
            try:
                logger.debug("[>] Switching to RX mode...")
                
                # CRITICAL FIX: Clear any pending data in buffers first
                try:
                    self._flush_buffers()
                except Exception as flush_error:
                    logger.debug(f"[!] Buffer flush warning: {flush_error}")
                
                # Send RX command with error handling
                try:
                    self.ser.write(b"RX\n")
                    self.ser.flush()
                except serial.SerialTimeoutException:
                    logger.warning("[!] Write timeout on first RX command, retrying...")
                    time.sleep(0.2)
                    # Try one more time
                    try:
                        self.ser.write(b"RX\n")
                        self.ser.flush()
                    except serial.SerialTimeoutException:
                        # If still timing out, the Pico might be busy
                        # Give it more time and assume RX will work
                        logger.warning("[!] Write timeout persists - Pico may be busy")
                        time.sleep(0.5)

                lines = self._collect_lines(timeout=0.5)

                if any(l == "OK:RX" for l in lines):
                    self.current_mode = "RX"
                    logger.info("[+] ✓ RX mode active")
                    return True

                # CRITICAL FIX: If no OK:RX but no errors either, assume success
                # This handles cases where the Pico was already in RX mode
                if not any(l.startswith("ERROR:") for l in lines):
                    logger.warning("[!] No OK:RX response, but no errors - assuming RX mode active")
                    self.current_mode = "RX"
                    return True

                logger.error(f"[X] RX mode failed, got lines: {lines}")
                return False
         
            except serial.SerialTimeoutException as e:
                logger.error(f"[X] RX mode write timeout: {e}")
                # Try to recover by setting current_mode anyway
                logger.warning("[!] Attempting recovery - assuming RX mode active")
                self.current_mode = "RX"
                return True
                
            except Exception as e:
                logger.error(f"[X] RX mode error: {e}")
                return False
    
    def send_message(self, message: str) -> bool:
        """
        Send message immediately via LoRa (BLOCKING operation)
        MUST be in TX mode first!
        NO MESSAGE QUEUING - sends immediately or fails
        """
        if not self.is_connected():
            logger.error("[X] Cannot send - not connected")
            return False
        
        try:
            with self.lock:
                if not self.is_connected():
                    return False
                
                # CRITICAL: Must be in TX mode
                if self.current_mode != "TX":
                    logger.error("[X] Cannot send - not in TX mode (use set_tx_mode() first)")
                    return False
                
                # Truncate if too long
                if len(message) > 255:
                    logger.warning(f"[!] Message too long ({len(message)} bytes), truncating to 255")
                    message = message[:255]
                
                logger.debug(f"[>] Sending {len(message)} bytes...")
                
                cmd = f"SEND:{message}\n"
                self.ser.write(cmd.encode())
                self.ser.flush()
                
                lines = self._collect_lines(timeout=15.0)

                # Accept OK:SENT anywhere in the response window
                for line in lines:
                    if line.strip() == "OK:SENT":
                        logger.info(f"[>] ✓ Transmitted {len(message)} bytes")
                        return True

                errors = [l for l in lines if l.startswith("ERROR:")]
                if errors:
                    logger.error(f"[X] Send failed: {errors}")
                    return False

                logger.error(f"[X] Send timeout or unexpected response: {lines}")
                return False
                    
        except Exception as e:
            logger.error(f"[X] Send error: {e}")
            return False
    
    def send_packet(self, packet_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Convenience method: send a dictionary as JSON
        MUST be in TX mode first!
        Returns: (success, msg_id)
        """
        # Add required fields
        if "msg_id" not in packet_dict:
            packet_dict["msg_id"] = generate_msg_id()
        
        if "from" not in packet_dict:
            packet_dict["from"] = CODENAME
        
        if "ttl" not in packet_dict:
            packet_dict["ttl"] = DEFAULT_TTL
        
        if "via" not in packet_dict:
            packet_dict["via"] = []
        
        json_str = json.dumps(packet_dict, separators=(',', ':'))
        return self.send_message(json_str), packet_dict["msg_id"]
    
    def receive_message(self, timeout: float = 0.5) -> Optional[str]:
        """
        Receive message from LoRa (only works in RX mode)
        Non-blocking with timeout
        """
        if not self.is_connected():
            return None
        
        try:
            with self.lock:
                if not self.is_connected():
                    return None
                
                # Can only receive in RX mode (HALF DUPLEX)
                if self.current_mode != "RX":
                    return None
                    
                start_time = time.time()
                while time.time() - start_time < timeout:
                    if self.ser.in_waiting:
                        chunk = self.ser.read(self.ser.in_waiting)
                        data = chunk.decode("utf-8", errors="replace")
                        for line in data.splitlines():
                            line = line.strip()

                            # Drop noise immediately
                            if not line:
                                continue

                            if line.startswith("DEBUG:"):
                                logger.debug(f"[PICO-DEBUG] {line}")
                                continue

                            if line.startswith(("OK:", "MODE:", "ERROR:", "RELAY:", "SPDT_", "LORA_", "BRIDGE_", "INIT_")):
                                continue

                            # ONLY RX lines are buffered
                            if line.startswith("RX:"):
                                self.rx_buffer += line + "\n"
                        
                            if len(self.rx_buffer) > RX_BUFFER_MAX:
                                logger.warning("[!] RX buffer trimmed")
                                self.rx_buffer = self.rx_buffer[-RX_BUFFER_MAX:]
                    else:
                        time.sleep(0.01)

                    # Process complete lines
                    if '\n' in self.rx_buffer:
                        line, self.rx_buffer = self.rx_buffer.split('\n', 1)
                        line = line.strip()
                        
                        # Skip DEBUG messages
                        if line.startswith("DEBUG:"):
                            logger.debug(f"[PICO-DEBUG] {line}")
                            continue
                        
                        # Only process RX: lines (LoRa data)
                        if line.startswith("RX:"):
                            content = line[3:]
                            
                            try:
                                parts = content.split('|')
                                if len(parts) >= 3:
                                    json_part = parts[0]
                                    rssi_part = parts[1]
                                    snr_part = parts[2]
                                    
                                    rssi = int(rssi_part.split(':')[1])
                                    snr = float(snr_part.split(':')[1])
                                    
                                    # Inject RSSI/SNR
                                    packet = json.loads(json_part)
                                    packet['rssi'] = rssi
                                    packet['snr'] = snr
                                    
                                    logger.info(f"[<] ✓ Received (RSSI:{rssi} SNR:{snr:.1f})")
                                    return json.dumps(packet)
                                else:
                                    return content
                                    
                            except json.JSONDecodeError:
                                logger.error(f"[X] Invalid JSON: {content[:50]}")
                                return None
                            except Exception as e:
                                logger.error(f"[X] Parse error: {e}")
                                return content
                        
                        # Ignore status messages
                        elif line.startswith(("OK:", "ERROR:", "MODE:", "LORA_", "BRIDGE_", "INIT_", "RELAY:", "SPDT_")):
                            continue
                            
        except Exception as e:
            if not self.is_reconnecting:
                logger.error(f"[X] Receive error: {e}")
        
        return None
    
    def _collect_lines(self, timeout: float = 2.0):
        """
        Collect all complete lines from serial for a duration.
        Returns a list of stripped lines.
        """
        lines = []
        buffer = ""
        start = time.time()

        while time.time() - start < timeout:
            if self.ser.in_waiting:
                chunk = self.ser.read(self.ser.in_waiting).decode("utf-8", errors="replace")
                buffer += chunk

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        lines.append(line)
            else:
                time.sleep(0.01)

        return lines


    def get_status(self) -> Optional[Dict[str, str]]:
        """Query Pico status"""
        if not self.is_connected():
            return None
            
        try:
            with self.lock:
                self.ser.write(b"STATUS\n")
                self.ser.flush()
                
                response = self._wait_for_response("MODE:", timeout=1.0, skip_debug=True)
                
                if response and response.startswith("MODE:"):
                    mode = response.split(':')[1].strip()
                    return {'mode': mode}
        except Exception as e:
            logger.error(f"[X] Status query error: {e}")
        
        return None
    
    def test_communication(self) -> bool:
        """Test Pico communication"""
        logger.info("\n" + "="*60)
        logger.info("PICO COMMUNICATION TEST - HALF DUPLEX")
        logger.info("="*60)
        
        if not self.is_connected():
            logger.error("[X] Not connected")
            return False
        
        try:
            with self.lock:
                # Test 1: STATUS
                logger.info("\n[TEST 1] STATUS command")
                self.ser.write(b"STATUS\n")
                self.ser.flush()
                time.sleep(0.2)
                
                resp = self._wait_for_response("MODE:", timeout=2.0, skip_debug=True)
                if resp:
                    logger.info(f"  ✓ PASS: {resp}")
                else:
                    logger.error("  ✗ FAIL: No response")
                    return False
                
                time.sleep(0.5)
                
                # Test 2: TX mode switch
                logger.info("\n[TEST 2] Switch to TX mode")
                if self.set_tx_mode():
                    logger.info(f"  ✓ PASS: TX mode active")
                else:
                    logger.error("  ✗ FAIL: TX mode failed")
                    return False
                
                time.sleep(0.5)
                
                # Test 3: Simple send
                logger.info("\n[TEST 3] Send test message")
                test_msg = '{"test":1}'
                cmd = f"SEND:{test_msg}\n"
                
                self.ser.write(cmd.encode())
                self.ser.flush()
                
                resp = self._wait_for_response("OK:SENT", timeout=6.0, skip_debug=True)
                if resp == "OK:SENT":
                    logger.info(f"  ✓ PASS: Message sent")
                else:
                    logger.error(f"  ✗ FAIL: {resp}")
                    return False
                
                time.sleep(0.5)
                
                # Test 4: Return to RX
                logger.info("\n[TEST 4] Switch to RX mode")
                if self.set_rx_mode():
                    logger.info(f"  ✓ PASS: RX mode active")
                else:
                    logger.error("  ✗ FAIL: RX mode failed")
                    return False
                
                logger.info("\n" + "="*60)
                logger.info("✓ ALL TESTS PASSED - HALF DUPLEX WORKING")
                logger.info("="*60 + "\n")
                return True
                
        except Exception as e:
            logger.error(f"\n[X] Test error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def close(self):
        """Close serial connection"""
        with self.lock:
            if self.ser:
                try:
                    self.ser.write(b"ALLOFF\n")
                    self.ser.flush()
                    time.sleep(0.1)
                except:
                    pass
                
                try:
                    self.ser.close()
                    logger.info("[+] Connection closed")
                except:
                    pass
                
                self.ser = None
                self.connection_healthy = False
                self.initialized = False