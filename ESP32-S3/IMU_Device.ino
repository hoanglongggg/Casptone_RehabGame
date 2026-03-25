#include <Wire.h>
#include <LSM6DS3.h>
#include "MAX30105.h" 
#include "heartRate.h"

// Khởi tạo cảm biến
LSM6DS3 myIMU(I2C_MODE, 0x6A); 
MAX30105 particleSensor;

const byte RATE_SIZE = 4; 
byte rates[RATE_SIZE]; 
byte rateSpot = 0;
long lastBeat = 0; 
float beatsPerMinute;
int beatAvg;

void setup() {
  Serial.begin(115200);
  
  // Khởi tạo I2C cho chân 8 (SDA), 9 (SCL) của Super Mini
  Wire.begin(8, 9);

  // Kiểm tra LSM6DS3
  if (myIMU.begin() != 0) {
    Serial.println("Loi: Khong tim thay LSM6DS3!");
    pinMode(48, OUTPUT);
    digitalWrite(48, HIGH); // LED đỏ sáng nếu lỗi
    while(1);
  }

  // Kiểm tra MAX30102
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("Loi: Khong tim thay MAX30102!");
    while (1);
  }

  // Cấu hình thông số cho MAX30102
  particleSensor.setup(); 
  particleSensor.setPulseAmplitudeRed(0x0A); 
  particleSensor.setPulseAmplitudeGreen(0);  
}

void loop() {
  // 1. Đọc dữ liệu nhịp tim
  long irValue = particleSensor.getIR();

  if (checkForBeat(irValue) == true) {
    long delta = millis() - lastBeat;
    lastBeat = millis();
    beatsPerMinute = 60 / (delta / 1000.0);

    if (beatsPerMinute < 255 && beatsPerMinute > 20) {
      rates[rateSpot++] = (byte)beatsPerMinute;
      rateSpot %= RATE_SIZE;
      beatAvg = 0;
      for (byte x = 0 ; x < RATE_SIZE ; x++) beatAvg += rates[x];
      beatAvg /= RATE_SIZE;
    }
  }

  // 2. Đọc dữ liệu gia tốc (IMU)
  float ax = myIMU.readRawAccelX();
  float ay = myIMU.readRawAccelY();
  float az = myIMU.readRawAccelZ();

  // Tính toán góc nghiêng
  float roll = atan2(ay, az) * 180.0 / M_PI;
  float pitch = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / M_PI;

  // 3. In dữ liệu Serial Debug
  Serial.print("Roll:"); Serial.print(roll);
  Serial.print("\tPitch:"); Serial.print(pitch);
  Serial.print("\tBPM:"); Serial.print(beatAvg);
  
  if (irValue < 50000) {
    Serial.println("\t[Vui long dat tay len cam bien]");
  } else {
    Serial.println();
  }

  delay(20); 
}