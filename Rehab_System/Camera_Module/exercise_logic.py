import numpy as np
import time


class RepCounter:
    def get_elapsed_time(self):
        elapsed = time.time() - self.start_session_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes:02d}:{seconds:02d}"
    def __init__(self, up_threshold=45, down_threshold=150):
        self.up_threshold = up_threshold
        self.down_threshold = down_threshold
        self.start_session_time = time.time()  # Bắt đầu tính giờ buổi tập
        self.data = {
            "left": self._reset_stats(),
            "right": self._reset_stats()
        }

    def _reset_stats(self):
        return {
            "counter": 0,
            "status": "Down",
            "all_angles": [],
            "session_min": 180,
            "session_max": 0,
            "rep_durations": [],  # Lưu thời gian hoàn thành mỗi rep (giây)
            "last_rep_time": time.time()
        }

    def update(self, side, angle):
        side_data = self.data[side]
        side_data["all_angles"].append(angle)

        if angle < side_data["session_min"]: side_data["session_min"] = angle
        if angle > side_data["session_max"]: side_data["session_max"] = angle

        # Khi bắt đầu co (Bắt đầu 1 rep mới)
        if side_data["status"] == "Down" and angle < self.up_threshold:
            side_data["status"] = "Up"
            side_data["start_rep_clock"] = time.time()  # Đánh dấu lúc bắt đầu co

        # Khi hoàn thành duỗi (Kết thúc 1 rep)
        if side_data["status"] == "Up" and angle > self.down_threshold:
            side_data["status"] = "Down"
            side_data["counter"] += 1
            # Tính thời gian hoàn thành rep đó
            duration = time.time() - side_data["start_rep_clock"]
            side_data["rep_durations"].append(round(duration, 2))

        return side_data["counter"], side_data["status"]

    def get_summary(self, side):
        d = self.data[side]
        if not d["all_angles"]: return None

        total_session_time = time.time() - self.start_session_time
        avg_rep_time = np.mean(d["rep_durations"]) if d["rep_durations"] else 0

        return {
            "total_reps": d["counter"],
            "best_flexion": round(d["session_min"], 2),
            "best_extension": round(d["session_max"], 2),
            "avg_flexion": round(np.mean(d["all_angles"]), 2),
            "total_time": round(total_session_time, 2),  # Tổng thời gian tập (s)
            "avg_rep_time": round(avg_rep_time, 2)  # Thời gian TB mỗi rep (s)
        }