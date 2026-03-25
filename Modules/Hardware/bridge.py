import serial
import socket

# Cấu hình
SERIAL_PORT = 'COM5'  # Thay bằng cổng của bạn
BAUD_RATE = 115200
UDP_IP = "127.0.0.1"
UDP_PORT = 5005

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Đang chuyển dữ liệu từ {SERIAL_PORT} sang Unity...")

    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode('utf-8').strip()
            # Bắn dữ liệu sang Unity qua mạng nội bộ
            sock.sendto(data.encode(), (UDP_IP, UDP_PORT))
except Exception as e:
    print(f"Lỗi: {e}. Kiểm tra cổng COM hoặc cáp USB.")