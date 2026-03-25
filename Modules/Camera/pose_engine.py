import cv2
import importlib
import numpy as np

class PoseEngine:
    def __init__(self, complexity=1):
        # Khởi tạo MediaPipe một cách an toàn và rõ ràng lỗi cài đặt
        self.mp = self._load_mediapipe_for_pose()
        self.mp_pose = self.mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            model_complexity=complexity,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.mp_drawing = self.mp.solutions.drawing_utils

    @staticmethod
    def _load_mediapipe_for_pose():
        """
        Tránh lỗi kiểu: module 'mediapipe' has no attribute 'solutions'.

        Trường hợp thường gặp:
        - Cài nhầm package (vd `mediapipe-silicon` thay vì `mediapipe`)
        - Tồn tại file/folder local trùng tên `mediapipe` làm shadow import
        """
        candidates = ["mediapipe", "mediapipe_silicon"]
        collected_errors = []

        for name in candidates:
            try:
                mp = importlib.import_module(name)
                if hasattr(mp, "solutions") and hasattr(mp.solutions, "pose"):
                    return mp
                collected_errors.append(
                    f"{name}: thiếu `solutions.pose` (có solutions nhưng không có pose hoặc không có solutions)."
                )
            except Exception as e:
                collected_errors.append(f"{name}: import thất bại -> {e}")

        msg = "\n".join(collected_errors)
        raise RuntimeError(
            "Không khởi tạo được MediaPipe Pose vì import/package không đúng.\n"
            "Lỗi chi tiết:\n"
            f"{msg}\n\n"
            "Gợi ý xử lý trên Windows (Python 3.8-3.12):\n"
            "1) Kiểm tra có file/folder local tên `mediapipe.py` hoặc `mediapipe/` trong project không.\n"
            "2) Chạy lệnh pip để dọn package và cài đúng MediaPipe:\n"
            "   pip uninstall -y mediapipe mediapipe-silicon\n"
            "   pip install mediapipe\n"
            "Nếu vẫn lỗi, cho mình log đầy đủ của UI (thông báo error)."
        )

    def extract_landmarks(self, frame):
        results = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return results

    @staticmethod
    def calculate_angle(a, b, c):
        a, b, c = np.array(a), np.array(b), np.array(c)
        radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
        angle = np.abs(radians * 180.0 / np.pi)
        return angle if angle <= 180.0 else 360 - angle