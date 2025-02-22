import serial
import time

class OwlController:
    def __init__(self, port='/dev/ttyUSB0', baudrate=57600, timeout=1):  # updated baudrate to 57600
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
        except Exception as e:
            print(f"[ERROR] Failed to initialize serial connection: {e}")
        time.sleep(2)
    
    def send_command(self, command: str):
        try:
            self.ser.reset_input_buffer()  # clear serial input buffer
            self.ser.write(command.encode())
            time.sleep(0.1)
        except Exception as e:
            print(f"[ERROR] Error sending command '{command.strip()}': {e}")
    
    def set_motor_positions(self, pos1: int, pos2: int, pos3: int):
        command = f"[m,1,{pos1},2,{pos2},3,{pos3}]\n"
        self.send_command(command)
    
    def reset_posture(self):
        default = 2045
        self.set_motor_positions(default, default, default)
    
    def toggle_torque(self, on: bool):
        cmd = "[n]\n" if on else "[f]\n"
        self.send_command(cmd)
    
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
    
    # Updated movement methods re-mapped based on Processing code:
    def nodding(self):
        """
        tilt toward servo 1.
        - Servo 1 remains at the default (2045).
        - Servo 2 is increased.
        - Servo 3 is decreased.
        """
        default = 2045
        delta = 90
        pos1 = default         # Servo 1 remains neutral.
        pos2 = default + delta # Servo 2 tilts upward.
        pos3 = default - delta # Servo 3 tilts downward.
        self.set_motor_positions(pos1, pos2, pos3)
        time.sleep(1)
        self.reset_posture()
    
    def rotating(self):
        """
        uniform upward movement.
        """
        default = 2045
        delta = 70
        pos = default + delta  # All servos move upward equally.
        self.set_motor_positions(pos, pos, pos)
        time.sleep(1)
        self.reset_posture()
    
    def upright_posture(self):
        """
        tilt toward servo 3.
        - Servo 1 is increased.
        - Servo 2 is decreased.
        - Servo 3 remains at default.
        """
        default = 2045
        delta = 90
        pos1 = default + delta # Servo 1 tilts upward.
        pos2 = default - delta # Servo 2 tilts downward.
        pos3 = default         # Servo 3 remains neutral.
        self.set_motor_positions(pos1, pos2, pos3)
        time.sleep(1)
        self.reset_posture()
    
    def backward_posture(self):
        """
        uniform downward movement.
        """
        default = 2045
        delta = 90
        pos = default - delta  # All servos move downward equally.
        self.set_motor_positions(pos, pos, pos)
        time.sleep(1)
        self.reset_posture()
    
    def tilting(self):
        """
        tilt toward servo 2.
        - Servo 1 is decreased.
        - Servo 2 remains at the default.
        - Servo 3 is increased.
        """
        default = 2045
        delta = 90
        pos1 = default - delta # Servo 1 tilts downward.
        pos2 = default         # Servo 2 remains neutral.
        pos3 = default + delta # Servo 3 tilts upward.
        self.set_motor_positions(pos1, pos2, pos3)
        time.sleep(1)
        self.reset_posture()

if __name__ == "__main__":
    try:
        owl = OwlController(port='/dev/tty.usbserial-AB0MHXVL')
        owl.toggle_torque(True)
        for movement in [owl.nodding, owl.rotating, owl.upright_posture, owl.backward_posture, owl.tilting]:
            movement()
            time.sleep(1)
        owl.toggle_torque(False)
    except Exception as e:
        print(f"[ERROR] Exception during demo: {e}")
