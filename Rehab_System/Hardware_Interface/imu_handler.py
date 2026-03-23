import serial
import socket
import time

class IMUHandler:
    def __init__(self, port='COM5', baudrate=115200):
        self.ser = serial.Serial(port, baudrate, timeout=1)
        self.udp_ip = "127.0.0.1"
        self.udp_port = 5005
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def start_streaming(self):
        print("Đang đọc dữ liệu IMU...")
        while True:
            if self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8').strip()
                    # Gửi dữ liệu "roll,pitch" sang Unity
                    self.sock.sendto(line.encode(), (self.udp_ip, self.udp_port))
                except:
                    pass
            time.sleep(0.01) # Tránh quá tải CPU