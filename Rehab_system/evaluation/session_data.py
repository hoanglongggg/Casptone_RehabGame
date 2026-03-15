import csv
import os
from datetime import datetime


class EvaluationLogger:
    def __init__(self, user_id="User_Unknown"):
        self.user_id = user_id
        # Tạo đường dẫn Database/Profiles/Ten_Nguoi_Dung
        self.folder = os.path.join("Database", "Profiles", user_id)
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)

    def save_medical_report(self, left_stats, right_stats):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(self.folder, f"Medical_Report_{timestamp}.csv")

        with open(filename, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['CHỈ SỐ TẬP LUYỆN', 'TAY TRÁI (Left)', 'TAY PHẢI (Right)'])

            def get_v(stats, key, unit=""):
                val = stats[key] if stats else "N/A"
                return f"{val} {unit}" if val != "N/A" else val

            writer.writerow(['Tổng thời gian tập', get_v(left_stats, "total_time", "giây"),
                             get_v(right_stats, "total_time", "giây")])
            writer.writerow(['Thời gian TB/lần lặp', get_v(left_stats, "avg_rep_time", "giây"),
                             get_v(right_stats, "avg_rep_time", "giây")])
            writer.writerow(
                ['Tổng số lần lặp (Reps)', get_v(left_stats, "total_reps"), get_v(right_stats, "total_reps")])
            writer.writerow(
                ['Độ co sâu nhất', get_v(left_stats, "best_flexion", "độ"), get_v(right_stats, "best_flexion", "độ")])
            writer.writerow(['Độ duỗi tốt nhất', get_v(left_stats, "best_extension", "độ"),
                             get_v(right_stats, "best_extension", "độ")])
            writer.writerow(
                ['Trung bình độ co', get_v(left_stats, "avg_flexion", "độ"), get_v(right_stats, "avg_flexion", "độ")])

        print(f"--- Đã lưu hồ sơ bệnh nhân tại: {filename} ---")