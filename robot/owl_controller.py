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
    
    # 1. Tilt Front
    def tilt_front(self):
        default = 2045
        delta = 90
        pos1 = default
        pos2 = default + delta
        pos3 = default - delta
        self.set_motor_positions(pos1, pos2, pos3)
        time.sleep(1)
        self.reset_posture()
    
    # 2. Tilt Back
    def tilt_back(self):
        default = 2045
        delta = 90
        pos1 = default
        pos2 = default - delta
        pos3 = default + delta
        self.set_motor_positions(pos1, pos2, pos3)
        time.sleep(1)
        self.reset_posture()
    
    # 3. Rotate Right
    def rotate_right(self):
        default = 2045
        delta = -90
        pos = default + delta  # All servos move upward equally.
        self.set_motor_positions(pos, pos, pos)
        time.sleep(1)
        self.reset_posture()
    
    # 4. Rotate Left
    def rotate_left(self):
        default = 2045
        delta = 90
        pos = default + delta  # All servos move upward equally.
        self.set_motor_positions(pos, pos, pos)
        time.sleep(1)
        self.reset_posture()
    
    # 5. Tilt Right
    def tilt_right(self):
        default = 2045
        delta = 90
        pos1 = default + delta
        pos2 = default
        pos3 = default - delta
        self.set_motor_positions(pos1, pos2, pos3)
        time.sleep(1)
        self.reset_posture()
    
    # 6. Tilt Left
    def tilt_left(self):
        default = 2045
        delta = 90
        pos1 = default - delta
        pos2 = default
        pos3 = default + delta
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
