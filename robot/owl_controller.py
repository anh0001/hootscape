import serial
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger("owl_controller")

class OwlController:
    def __init__(self, port='/dev/ttyUSB0', baudrate=57600, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="owl_serial")
        self.lock = threading.Lock()
        self.connected = False
        
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            self.connected = True
            logger.info(f"Serial connection established on {port}")
        except Exception as e:
            logger.error(f"Failed to initialize serial connection: {e}")
            self.connected = False
        
        time.sleep(2)
    
    def _send_command_sync(self, command: str):
        """Synchronous command sending - runs in thread executor"""
        if not self.connected or not self.ser:
            logger.warning(f"Serial not connected, skipping command: {command.strip()}")
            return False
            
        try:
            with self.lock:
                self.ser.reset_input_buffer()
                self.ser.write(command.encode())
                time.sleep(0.1)
            return True
        except Exception as e:
            logger.error(f"Error sending command '{command.strip()}': {e}")
            # Try to reconnect
            self._reconnect()
            return False
    
    def _reconnect(self):
        """Attempt to reconnect to the serial device"""
        try:
            if self.ser:
                self.ser.close()
        except:
            pass
            
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.connected = True
            logger.info("Serial connection re-established")
        except Exception as e:
            logger.error(f"Failed to reconnect: {e}")
            self.connected = False
    
    async def send_command(self, command: str):
        """Async wrapper for command sending"""
        loop = asyncio.get_event_loop()
        try:
            # Use executor to prevent blocking the event loop
            result = await asyncio.wait_for(
                loop.run_in_executor(self.executor, self._send_command_sync, command),
                timeout=2.0  # 2-second timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Command timeout: {command.strip()}")
            return False
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return False
    
    async def set_motor_positions(self, pos1: int, pos2: int, pos3: int):
        command = f"[m,1,{pos1},2,{pos2},3,{pos3}]\n"
        return await self.send_command(command)
    
    async def reset_posture(self):
        default = 2045
        return await self.set_motor_positions(default, default, default)
    
    async def toggle_torque(self, on: bool):
        cmd = "[n]\n" if on else "[f]\n"
        return await self.send_command(cmd)
    
    def set_speed(self, speed: str):
        cmd = f"[v,{speed}]\n"
        self.send_command(cmd)
    
    def get_positions(self):
        try:
            self.send_command("[g]\n")  # assuming [g] for GET in Processing protocol
            response = self.ser.readline().decode().strip()
            return response
        except Exception as e:
            print(f"[ERROR] Error reading positions: {e}")
            return None
    
    # Updated movement methods to be async and non-blocking
    async def tilt_front(self):
        default = 2045
        delta = 90
        pos1 = default
        pos2 = default + delta
        pos3 = default - delta
        
        await self.set_motor_positions(pos1, pos2, pos3)
        # Use asyncio.sleep instead of time.sleep
        await asyncio.sleep(1)
        await self.reset_posture()
    
    async def tilt_back(self):
        default = 2045
        delta = 90
        pos1 = default
        pos2 = default - delta
        pos3 = default + delta
        
        await self.set_motor_positions(pos1, pos2, pos3)
        await asyncio.sleep(1)
        await self.reset_posture()
    
    async def rotate_right(self):
        default = 2045
        delta = -90
        pos = default + delta
        
        await self.set_motor_positions(pos, pos, pos)
        await asyncio.sleep(1)
        await self.reset_posture()
    
    async def rotate_left(self):
        default = 2045
        delta = 90
        pos = default + delta
        
        await self.set_motor_positions(pos, pos, pos)
        await asyncio.sleep(1)
        await self.reset_posture()
    
    async def tilt_right(self):
        default = 2045
        delta = 90
        pos1 = default + delta
        pos2 = default
        pos3 = default - delta
        
        await self.set_motor_positions(pos1, pos2, pos3)
        await asyncio.sleep(1)
        await self.reset_posture()
    
    async def tilt_left(self):
        default = 2045
        delta = 90
        pos1 = default - delta
        pos2 = default
        pos3 = default + delta
        
        await self.set_motor_positions(pos1, pos2, pos3)
        await asyncio.sleep(1)
        await self.reset_posture()
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up owl controller...")
        self.connected = False
        
        # Shutdown executor
        if self.executor:
            self.executor.shutdown(wait=False)
        
        # Close serial connection
        if self.ser:
            try:
                self.ser.close()
                logger.info("Serial connection closed")
            except Exception as e:
                logger.error(f"Error closing serial connection: {e}")
    
    def __del__(self):
        """Destructor"""
        try:
            self.cleanup()
        except:
            pass

if __name__ == "__main__":
    async def demo():
        try:
            owl = OwlController(port='/dev/tty.usbserial-AB0MHXVL')
            await owl.toggle_torque(True)
            for movement in [owl.tilt_front, owl.tilt_back, owl.rotate_right, owl.rotate_left, owl.tilt_right, owl.tilt_left]:
                await movement()
                await asyncio.sleep(1)
            await owl.toggle_torque(False)
            owl.cleanup()
        except Exception as e:
            logger.error(f"Exception during demo: {e}")
    
    asyncio.run(demo())
