import ctypes
import time

import cv2
from PySide6.QtCore import QThread, Signal

from Modules.Camera.pose_engine import PoseEngine
from Modules.Camera.exercise_logic import RepCounter


def _format_mm_ss(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


class CameraWorker(QThread):
    """
    Worker xử lý Camera + MediaPipe + RepCounter.

    - Không ghi Database trực tiếp trong worker (thread-safe): UI sẽ lưu DB khi nhận `summary_ready`.
    - Cơ chế dừng an toàn: dùng cờ `self.running` để thoát vòng lặp và `release()` VideoCapture.
    """

    # stats_update(int reps, str status)
    stats_update = Signal(int, str)

    # summary_ready(dict summary)
    summary_ready = Signal(dict)

    # error(str message)
    error = Signal(str)

    def __init__(
        self,
        patient_id: int,
        game_name: str,
        max_duration_sec: int | None = 60,
        camera_index: int = 0,
        mirror_for_display: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.patient_id = patient_id
        self.game_name = game_name
        # max_duration_sec:
        # - None hoặc 0: chạy vô hạn cho tới khi request_stop() được gọi
        # - > 0: chạy tối đa số giây tương ứng
        if max_duration_sec is None or float(max_duration_sec) <= 0:
            self.max_duration_sec = None
        else:
            self.max_duration_sec = int(max_duration_sec)
        self.camera_index = int(camera_index)

        # Theo yêu cầu: dùng cờ biến để dừng an toàn
        self.running = False
        self.mirror_for_display = bool(mirror_for_display)

        # OpenCV window
        self.window_name = "Hinh anh tap luyen"

    @staticmethod
    def _get_screen_size() -> tuple[int, int]:
        """
        Lấy (width, height) màn hình hiện tại trên Windows.
        Ưu tiên:
        - `screeninfo` nếu có
        - `pyautogui` nếu có
        - fallback ctypes
        """
        try:
            # Optional: screeninfo
            try:
                from screeninfo import get_monitors  # type: ignore

                monitors = get_monitors()
                if monitors:
                    m0 = monitors[0]
                    return int(m0.width), int(m0.height)
            except Exception:
                pass

            # Optional: pyautogui
            try:
                import pyautogui  # type: ignore

                w, h = pyautogui.size()
                return int(w), int(h)
            except Exception:
                pass

            user32 = ctypes.windll.user32
            width = int(user32.GetSystemMetrics(0))
            height = int(user32.GetSystemMetrics(1))
            return width, height
        except Exception:
            # Fallback nếu không lấy được kích thước màn hình
            return 1280, 720

    def request_stop(self) -> None:
        """
        Dừng worker. Worker sẽ thoát vòng lặp và giải phóng camera.
        """
        self.running = False

    def run(self) -> None:
        """
        Vòng lặp chính:
        - Đọc frame từ camera
        - PoseEngine trích landmark
        - RepCounter cập nhật góc/đếm reps
        - Emit `stats_update` định kỳ
        - Kết thúc: emit `summary_ready`
        """
        cap = None
        pose_engine = None
        rep_counter = None
        window_configured = False

        try:
            self.running = True

            pose_engine = PoseEngine()
            rep_counter = RepCounter()

            start_ts = time.time()
            elapsed = 0.0
            end_ts = None if self.max_duration_sec is None else (start_ts + self.max_duration_sec)

            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                self.error.emit("Không mở được camera. Vui lòng kiểm tra camera/permission.")
                return

            # Khởi tạo cửa sổ OpenCV
            try:
                cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
                # Luôn ở trên cùng (Topmost)
                cv2.setWindowProperty(self.window_name, cv2.WND_PROP_TOPMOST, 1)
            except Exception:
                # Nếu hệ thống không hỗ trợ GUI (headless) thì báo lỗi rõ cho UI
                self.error.emit("OpenCV không tạo được cửa sổ camera (imshow/namedWindow thất bại).")
                self.running = False
                return

            last_emit_ts = 0.0

            # Landmark indices (MediaPipe Pose):
            # left arm: shoulder=11, elbow=13, wrist=15
            # right arm: shoulder=12, elbow=14, wrist=16
            vis_thr = 0.5

            while self.running and (end_ts is None or time.time() < end_ts):
                ok, frame = cap.read()
                if not ok:
                    elapsed = time.time() - start_ts
                    continue

                results = pose_engine.extract_landmarks(frame)

                if results.pose_landmarks:
                    lm = results.pose_landmarks.landmark

                    # Vẽ landmark lên frame để bệnh nhân nhìn thấy
                    try:
                        if hasattr(pose_engine, "mp_drawing") and hasattr(pose_engine, "mp_pose"):
                            pose_engine.mp_drawing.draw_landmarks(
                                frame,
                                results.pose_landmarks,
                                pose_engine.mp_pose.POSE_CONNECTIONS,
                            )
                    except Exception:
                        # Không làm hỏng luồng nếu việc vẽ landmark lỗi
                        pass

                    # Left angle (elbow)
                    if lm[11].visibility > vis_thr and lm[13].visibility > vis_thr and lm[15].visibility > vis_thr:
                        a = (lm[11].x, lm[11].y)
                        b = (lm[13].x, lm[13].y)
                        c = (lm[15].x, lm[15].y)
                        angle_left = PoseEngine.calculate_angle(a, b, c)
                        rep_counter.update("left", angle_left)

                    # Right angle (elbow)
                    if lm[12].visibility > vis_thr and lm[14].visibility > vis_thr and lm[16].visibility > vis_thr:
                        a = (lm[12].x, lm[12].y)
                        b = (lm[14].x, lm[14].y)
                        c = (lm[16].x, lm[16].y)
                        angle_right = PoseEngine.calculate_angle(a, b, c)
                        rep_counter.update("right", angle_right)

                elapsed = time.time() - start_ts

                # Hiển thị ảnh camera
                # - Mirror để người tập thấy giống gương
                # - Chia màn hình: camera chiếm 1/4 bên phải
                try:
                    show_frame = frame
                    if self.mirror_for_display:
                        show_frame = cv2.flip(show_frame, 1)

                    cv2.imshow(self.window_name, show_frame)

                    if not window_configured:
                        # Cấu hình resize + move ngay khi có frame đầu tiên
                        screen_w, screen_h = self._get_screen_size()
                        cam_w = max(320, int(screen_w * 0.25))
                        cam_h = int(screen_h)
                        x = screen_w - cam_w
                        y = 0

                        # Topmost + resize/move (Windows)
                        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_TOPMOST, 1)
                        try:
                            cv2.resizeWindow(self.window_name, cam_w, cam_h)
                        except Exception:
                            # Một số build OpenCV có thể không hỗ trợ resizeWindow
                            pass
                        try:
                            cv2.moveWindow(self.window_name, x, y)
                        except Exception:
                            pass
                        window_configured = True
                    else:
                        # Đảm bảo luôn topmost (tránh bị che khi focus sang game)
                        try:
                            cv2.setWindowProperty(self.window_name, cv2.WND_PROP_TOPMOST, 1)
                        except Exception:
                            pass

                    # Bắt sự kiện UI của OpenCV
                    cv2.waitKey(1)
                except cv2.error as e:
                    self.error.emit(f"OpenCV imshow lỗi: {e}")
                    self.running = False
                    break
                except Exception as e:
                    self.error.emit(f"Lỗi hiển thị camera: {e}")
                    self.running = False
                    break

                # Emit định kỳ để UI không bị spam mỗi frame
                now = time.time()
                if (now - last_emit_ts) >= 0.3:
                    last_emit_ts = now

                    left_reps = int(rep_counter.data["left"]["counter"])
                    right_reps = int(rep_counter.data["right"]["counter"])

                    total_reps = max(left_reps, right_reps)
                    chosen_side = "left" if left_reps >= right_reps else "right"
                    status = rep_counter.data[chosen_side]["status"]

                    self.stats_update.emit(
                        total_reps,
                        f"{chosen_side} | {status} | t={_format_mm_ss(elapsed)}",
                    )

            # Tổng kết
            left_summary = rep_counter.get_summary("left")
            right_summary = rep_counter.get_summary("right")

            def _total_reps(summary_dict):
                if not summary_dict:
                    return 0
                return int(summary_dict.get("total_reps", 0))

            left_reps = _total_reps(left_summary)
            right_reps = _total_reps(right_summary)

            chosen_summary = left_summary if left_reps >= right_reps else right_summary
            chosen_reps = left_reps if left_reps >= right_reps else right_reps

            if not chosen_summary:
                chosen_summary = {
                    "avg_flexion": 0.0,
                    "total_time": float(elapsed),
                    "total_reps": chosen_reps,
                }

            self.summary_ready.emit(
                {
                    "patient_id": self.patient_id,
                    "game_name": self.game_name,
                    "reps": int(chosen_summary.get("total_reps", chosen_reps)),
                    "avg_flexion": float(chosen_summary.get("avg_flexion", 0.0)),
                    "duration": float(chosen_summary.get("total_time", elapsed)),
                }
            )
        except Exception as e:
            self.error.emit(f"Lỗi camera/MediaPipe: {e}")
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

            # Dọn dẹp cửa sổ OpenCV
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

