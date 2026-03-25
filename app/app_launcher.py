import sys
import os
import subprocess
import time

import cv2
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QThread, Signal

# Bảo đảm import module từ project root (app/ nằm dưới root)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Modules.Database.db_manager import DatabaseManager
from Modules.Camera.pose_engine import PoseEngine
from Modules.Camera.exercise_logic import RepCounter

# Worker & integration mới theo kiến trúc Worker-Interface
from Workers.camera_worker import CameraWorker as ExternalCameraWorker
from app.integration import (
    arrange_windows,
    start_bridge_subprocess as integration_start_bridge_subprocess,
    stop_bridge_subprocess as integration_stop_bridge_subprocess,
)

# --- TÙY CHỈNH GIAO DIỆN (UI DESIGN TOKENS) ---
STYLE_SHEET = """
    QWidget { background-color: #121212; color: #E0E0E0; font-family: 'Segoe UI', Arial; }

    QFrame#Card { background-color: #1E1E1E; border-radius: 15px; padding: 20px; }

    QLabel#Header { font-size: 26px; font-weight: bold; color: #4aa3ff; margin-bottom: 10px; }
    QLabel#SubHeader { font-size: 16px; font-weight: bold; color: #BBBBBB; border: none; }

    QLineEdit, QTextEdit, QComboBox { 
        background-color: #2C2C2C; border: 1px solid #3D3D3D; border-radius: 8px; 
        padding: 10px; color: white; font-size: 14px;
    }
    QLineEdit:focus { border: 1px solid #4aa3ff; }

    QPushButton { border-radius: 10px; padding: 12px; font-weight: bold; font-size: 14px; }
    QPushButton#Primary { background-color: #1a73e8; color: white; }
    QPushButton#Primary:hover { background-color: #1557b0; }

    QPushButton#Success { background-color: #00C853; color: black; font-size: 18px; }
    QPushButton#Success:hover { background-color: #00E676; }

    QPushButton#Danger { background-color: #CF6679; color: white; font-size: 12px; padding: 6px 15px; }

    QTableWidget { background-color: #1E1E1E; gridline-color: #333; border: none; }
    QHeaderView::section { background-color: #2C2C2C; color: #4aa3ff; font-weight: bold; border: none; padding: 8px; }
"""


# --- HELPERS & WORKER (MULTI-MODULE INTEGRATION) ---
def format_mm_ss(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def _project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def start_bridge_subprocess() -> subprocess.Popen | None:
    """
    Chạy `Hardware_Interface/bridge.py` để nhận IMU qua Serial và đẩy lên Unity (UDP).

    Lưu ý: `bridge.py` chạy vô hạn, nên cần kết thúc bằng `terminate()/kill()`.
    """
    bridge_path = os.path.join(_project_root(), "Hardware_Interface", "bridge.py")
    if not os.path.exists(bridge_path):
        return None

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        return subprocess.Popen(
            [sys.executable, bridge_path],
            cwd=_project_root(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception:
        return None


def stop_bridge_subprocess(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


class CameraWorker(QThread):
    """
    QThread chạy camera + MediaPipe + RepCounter để tránh treo UI.
    """

    summary_ready = Signal(dict)
    stats_update = Signal(int, int, float)  # left_reps, right_reps, elapsed_sec
    error = Signal(str)

    def __init__(
        self,
        patient_id: int,
        game_name: str,
        max_duration_sec: int = 60,
        camera_index: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.patient_id = patient_id
        self.game_name = game_name
        self.max_duration_sec = max_duration_sec
        self.camera_index = camera_index
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        pose_engine = PoseEngine()
        rep_counter = RepCounter()
        start_ts = time.time()
        now = start_ts

        cap = None
        try:
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                self.error.emit("Không mở được camera.")
                return

            last_ui_ts = 0.0
            while not self._stop_requested and (time.time() - start_ts) < self.max_duration_sec:
                ok, frame = cap.read()
                if not ok:
                    continue

                results = pose_engine.extract_landmarks(frame)
                if results.pose_landmarks:
                    lm = results.pose_landmarks.landmark

                    # Góc khuỷu (shoulder-elbow-wrist) cho cả 2 tay.
                    # Landmark index (MediaPipe Pose):
                    # left: 11 (shoulder), 13 (elbow), 15 (wrist)
                    # right: 12 (shoulder), 14 (elbow), 16 (wrist)
                    vis_thr = 0.5

                    if (
                        lm[11].visibility > vis_thr
                        and lm[13].visibility > vis_thr
                        and lm[15].visibility > vis_thr
                    ):
                        a = (lm[11].x, lm[11].y)
                        b = (lm[13].x, lm[13].y)
                        c = (lm[15].x, lm[15].y)
                        angle_left = PoseEngine.calculate_angle(a, b, c)
                        rep_counter.update("left", angle_left)

                    if (
                        lm[12].visibility > vis_thr
                        and lm[14].visibility > vis_thr
                        and lm[16].visibility > vis_thr
                    ):
                        a = (lm[12].x, lm[12].y)
                        b = (lm[14].x, lm[14].y)
                        c = (lm[16].x, lm[16].y)
                        angle_right = PoseEngine.calculate_angle(a, b, c)
                        rep_counter.update("right", angle_right)

                # Cập nhật UI nhẹ nhàng (không spam signal)
                now = time.time()
                if now - last_ui_ts >= 0.5:
                    last_ui_ts = now
                    left_reps = rep_counter.data["left"]["counter"]
                    right_reps = rep_counter.data["right"]["counter"]
                    self.stats_update.emit(left_reps, right_reps, now - start_ts)

            # Tổng kết cuối session
            left_summary = rep_counter.get_summary("left")
            right_summary = rep_counter.get_summary("right")

            chosen_side = None
            chosen = None
            if left_summary and right_summary:
                if left_summary["total_reps"] >= right_summary["total_reps"]:
                    chosen_side = "left"
                    chosen = left_summary
                else:
                    chosen_side = "right"
                    chosen = right_summary
            elif left_summary:
                chosen_side = "left"
                chosen = left_summary
            elif right_summary:
                chosen_side = "right"
                chosen = right_summary

            if chosen is None:
                chosen = {"total_reps": 0, "avg_flexion": 0.0, "total_time": time.time() - start_ts}
                chosen_side = "none"

            self.summary_ready.emit(
                {
                    "patient_id": self.patient_id,
                    "game_name": self.game_name,
                    "side": chosen_side,
                    "reps": int(chosen["total_reps"]),
                    "avg_flexion": float(chosen["avg_flexion"]),
                    "duration": float(chosen["total_time"]),
                }
            )
        except Exception as e:
            self.error.emit(f"Lỗi camera/mediapipe: {e}")
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass


# --- MÀN HÌNH CHỌN GAME ---
class GameSelection(QWidget):
    def __init__(self, db, patient_id, patient_name, on_back):
        super().__init__()
        self.db = db
        self.patient_id = patient_id
        self.patient_name = patient_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        btn_back = QPushButton("← Quay lại Menu");
        btn_back.setFixedWidth(150)
        btn_back.clicked.connect(self.handle_back);
        layout.addWidget(btn_back)

        title = QLabel(f"BÀI TẬP CHO: {patient_name.upper()}")
        title.setObjectName("Header");
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(20)

        # Chỉ còn 1 game thực tế: Game Chim Bay
        self.game_btn = QPushButton("🎮 Game Chim Bay")
        self.game_btn.setFixedHeight(80)
        self.game_btn.setStyleSheet(
            "background-color: #2C2C2C; font-size: 18px; text-align: left; padding-left: 30px;"
        )
        self.game_btn.clicked.connect(self.start_game_chim_bay)
        layout.addWidget(self.game_btn)

        self.lbl_status = QLabel("Chọn 1 game để bắt đầu.")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setObjectName("SubHeader")
        layout.addWidget(self.lbl_status)

        self.btn_stop = QPushButton("⏹ Kết thúc tập")
        self.btn_stop.setObjectName("Danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(lambda: self.stop_and_maybe_save(navigate_back_after=False))
        layout.addWidget(self.btn_stop)

        layout.addSpacing(10)
        self._active_game_key = None
        self._pending_navigation_back = False
        # Worker mới theo kiến trúc: chỉ dùng ExternalCameraWorker
        self.camera_worker: ExternalCameraWorker | None = None
        self.bridge_proc: subprocess.Popen | None = None
        self.game_proc: subprocess.Popen | None = None
        self.on_back = on_back
        layout.addStretch()

    def start_game_chim_bay(self) -> None:
        """
        Bấm vào nút Game Chim Bay:
        - Khởi chạy bridge.py (subprocess) song song
        - Khởi chạy CameraWorker để tính reps/avg_flexion/duration
        - Khởi chạy Games/GameChimBay.exe
        """
        # game_name (lưu DB) và game_key (truyền vào worker)
        game_key = "GameChimBay"
        self._active_game_key = game_key
        self.start_game(game_key)

    def start_game(self, game_key: str):
        if self.camera_worker is not None and self.camera_worker.isRunning():
            return
        self._active_game_key = game_key

        # Disable nút game để tránh bấm nhiều lần
        self.game_btn.setEnabled(False)

        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("Đang khởi động camera + MediaPipe, đồng thời chạy bridge...")

        # 1) Subprocess bridge chạy song song
        self.bridge_proc = integration_start_bridge_subprocess()

        # 2) Khởi chạy Unity game thực tế
        try:
            game_exe_rel = os.path.join("Games", "GameChimBay.exe")
            game_exe_path = os.path.join(PROJECT_ROOT, game_exe_rel)
            if not os.path.exists(game_exe_path):
                raise FileNotFoundError(f"Không tìm thấy file game: {game_exe_path}")

            game_cwd = os.path.dirname(game_exe_path)
            # Không force no-window, để game tự hiển thị UI của nó.
            self.game_proc = subprocess.Popen([game_exe_path], cwd=game_cwd)

            # Sắp xếp màn hình: Game trái (3/4), Camera phải (1/4)
            # best-effort: cửa sổ Unity có thể mất chút thời gian để xuất hiện.
            try:
                arrange_windows("GameChimBay")
            except Exception:
                pass
        except Exception as e:
            # Nếu game không chạy thì vẫn cho camera chạy và ghi DB,
            # nhưng báo người dùng để họ kiểm tra đường dẫn game.
            self.lbl_status.setText(f"Khởi chạy game thất bại: {e}")
            self.game_proc = None

        # 3) QThread camera chạy để không treo UI
        self.camera_worker = ExternalCameraWorker(
            patient_id=self.patient_id,
            game_name=game_key,
            max_duration_sec=None,
            mirror_for_display=True,
        )
        self.camera_worker.stats_update.connect(self.on_stats_update)
        self.camera_worker.summary_ready.connect(self.on_camera_finished)
        self.camera_worker.error.connect(self.on_camera_error)
        self.camera_worker.start()

    # stats_update(int reps, str status)
    def on_stats_update(self, reps: int, status: str) -> None:
        self.lbl_status.setText(f"Đang tập... Reps: {reps} | {status}")

    def stop_and_maybe_save(self, navigate_back_after: bool) -> None:
        self._pending_navigation_back = bool(navigate_back_after)
        self.btn_stop.setEnabled(False)

        if self.camera_worker is not None and self.camera_worker.isRunning():
            self.lbl_status.setText("Đang dừng camera để lấy kết quả...")
            self.camera_worker.request_stop()
        else:
            # Nếu chưa chạy worker thì điều hướng ngay.
            if self._pending_navigation_back:
                self.on_back()

    def handle_back(self) -> None:
        # Nếu đang chạy tập thì dừng trước, sau đó mới quay về menu.
        if self.camera_worker is not None and self.camera_worker.isRunning():
            self.stop_and_maybe_save(navigate_back_after=True)
        else:
            self.on_back()

    def _re_enable_games(self) -> None:
        self.game_btn.setEnabled(True)

        # Thử tắt game nếu đang chạy để quay về menu mượt hơn
        if self.game_proc is not None:
            try:
                if self.game_proc.poll() is None:
                    self.game_proc.terminate()
            except Exception:
                pass
            self.game_proc = None

    def on_camera_error(self, msg: str) -> None:
        integration_stop_bridge_subprocess(self.bridge_proc)
        self.bridge_proc = None
        self._re_enable_games()

        QMessageBox.warning(self, "Lỗi", msg)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Đã dừng do lỗi. Chọn lại game khác.")

        if self._pending_navigation_back:
            self.on_back()
            self._pending_navigation_back = False

    def on_camera_finished(self, summary: dict) -> None:
        # 1) Dừng bridge sau khi tắt camera (đúng theo yêu cầu đồng bộ)
        integration_stop_bridge_subprocess(self.bridge_proc)
        self.bridge_proc = None
        self._re_enable_games()

        reps = summary.get("reps", 0)
        avg_flexion = summary.get("avg_flexion", 0.0)
        duration = summary.get("duration", 0.0)
        game_key = summary.get("game_name", self._active_game_key)

        # 2) Lưu session vào SQLite (DatabaseManager)
        try:
            self.db.add_session(self.patient_id, game_key, reps, avg_flexion, duration)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi DB", f"Không lưu được session: {e}")

        self.btn_stop.setEnabled(False)

        self.lbl_status.setText(
            f"Kết thúc! Reps: {reps} | Avg flexion: {avg_flexion:.2f} | Duration: {duration:.2f}s"
        )

        if self._pending_navigation_back:
            self.on_back()
            self._pending_navigation_back = False


# --- MÀN HÌNH CHI TIẾT HỒ SƠ ---
class ProfileWindow(QWidget):
    def __init__(self, db, p_id, on_back):
        super().__init__()
        self.db = db;
        self.p_id = p_id;
        self.on_back = on_back
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 25)

        # Header Navigation
        h = QHBoxLayout()
        btn_b = QPushButton("← Quay lại");
        btn_b.clicked.connect(self.on_back);
        h.addWidget(btn_b)
        h.addStretch();
        layout.addLayout(h)

        # Lấy data ban đầu
        p = self.db.get_patient_detail(self.p_id)

        self.lbl_title = QLabel(f"Hồ sơ: {p[2]} (ID: {p[0]})")
        self.lbl_title.setObjectName("Header");
        layout.addWidget(self.lbl_title)

        # Form thông tin
        card = QFrame();
        card.setObjectName("Card");
        v = QVBoxLayout(card)

        self.in_dis = QLineEdit(p[5] or "");
        self.in_dis.setPlaceholderText("Bệnh lý (ví dụ: Đột quỵ, liệt nửa người...)")
        self.in_con = QLineEdit(p[6] or "");
        self.in_con.setPlaceholderText("Tình trạng hiện tại (ví dụ: Tay co cứng...)")
        self.in_note = QTextEdit(p[7] or "");
        self.in_note.setPlaceholderText("Ghi chú tiến triển phục hồi...")
        self.in_note.setMaximumHeight(150)

        v.addWidget(QLabel("<b>BỆNH LÝ:</b>"))
        v.addWidget(self.in_dis)
        v.addWidget(QLabel("<b>TÌNH TRẠNG HIỆN TẠI:</b>"))
        v.addWidget(self.in_con)
        v.addWidget(QLabel("<b>NHẬN ĐỊNH CỦA BÁC SĨ:</b>"))
        v.addWidget(self.in_note)

        btn_up = QPushButton("LƯU CẬP NHẬT HỒ SƠ");
        btn_up.setObjectName("Primary")
        btn_up.clicked.connect(self.save_changes);
        v.addWidget(btn_up)
        layout.addWidget(card)

        # Bảng lịch sử
        layout.addWidget(QLabel("<br><b>LỊCH SỬ LUYỆN TẬP</b>"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Ngày tập", "Trò chơi", "Số Reps", "Góc TB", "T.Gian(s)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.refresh_table()

    def save_changes(self):
        self.db.update_patient(self.p_id, self.in_dis.text(), self.in_con.text(), self.in_note.toPlainText())
        QMessageBox.information(self, "Thành công", "Đã cập nhật thông tin bệnh nhân vào hệ thống!")

    def refresh_table(self):
        data = self.db.get_sessions(self.p_id)
        self.table.setRowCount(len(data))
        for r, row_data in enumerate(data):
            for c, val in enumerate(row_data):
                self.table.setItem(r, c, QTableWidgetItem(str(val)))


# --- MÀN HÌNH ĐĂNG NHẬP ---
class LoginWindow(QWidget):
    def __init__(self, db, on_success):
        super().__init__()
        self.db = db;
        self.on_success = on_success
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)

        title = QLabel("REHAB SYSTEM");
        title.setObjectName("Header");
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.u = QLineEdit();
        self.u.setPlaceholderText("Tên đăng nhập")
        self.p = QLineEdit();
        self.p.setPlaceholderText("Mật khẩu");
        self.p.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.u);
        layout.addWidget(self.p)

        btn_l = QPushButton("ĐĂNG NHẬP");
        btn_l.setObjectName("Primary");
        btn_l.clicked.connect(self.handle_l)
        layout.addWidget(btn_l)

        btn_r = QPushButton("Đăng ký bác sĩ mới");
        btn_r.setStyleSheet("border: none; color: #4aa3ff;");
        btn_r.clicked.connect(self.handle_r)
        layout.addWidget(btn_r)

    def handle_l(self):
        res = self.db.login(self.u.text(), self.p.text())
        if res:
            self.on_success(res[0], self.u.text())
        else:
            QMessageBox.warning(self, "Lỗi", "Sai thông tin tài khoản!")

    def handle_r(self):
        if self.u.text() and self.p.text():
            if self.db.add_account(self.u.text(), self.p.text()):
                QMessageBox.information(self, "Thành công", "Đã tạo tài khoản bác sĩ!")
            else:
                QMessageBox.warning(self, "Lỗi", "Tài khoản đã tồn tại!")


# --- MENU CHÍNH ---
class MainMenu(QWidget):
    def __init__(self, db, acc_id, user, ctrl):
        super().__init__()
        self.db = db;
        self.acc_id = acc_id;
        self.ctrl = ctrl
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 25)

        # Header
        h = QHBoxLayout()
        h.addWidget(QLabel(f"Bác sĩ: <b style='color:#4aa3ff'>{user.upper()}</b>"))
        h.addStretch()
        btn_out = QPushButton("Đăng xuất");
        btn_out.setObjectName("Danger");
        btn_out.clicked.connect(ctrl.show_login)
        h.addWidget(btn_out);
        layout.addLayout(h)

        # Card: Quản lý bệnh nhân
        card1 = QFrame();
        card1.setObjectName("Card");
        v1 = QVBoxLayout(card1)
        v1.addWidget(QLabel("<b>HỒ SƠ BỆNH NHÂN</b>"))
        self.cb_p = QComboBox();
        v1.addWidget(self.cb_p)
        btn_v = QPushButton("📄 XEM CHI TIẾT HỒ SƠ");
        btn_v.setObjectName("Primary");
        btn_v.clicked.connect(self.go_profile)
        v1.addWidget(btn_v);
        layout.addWidget(card1)

        # Card: Thêm bệnh nhân
        card2 = QFrame();
        card2.setObjectName("Card");
        v2 = QVBoxLayout(card2)
        v2.addWidget(QLabel("<b>THÊM HỒ SƠ MỚI</b>"))
        self.in_n = QLineEdit();
        self.in_n.setPlaceholderText("Tên bệnh nhân...")
        self.in_a = QLineEdit();
        self.in_a.setPlaceholderText("Tuổi...")
        v2.addWidget(self.in_n);
        v2.addWidget(self.in_a)
        btn_s = QPushButton("LƯU");
        btn_s.clicked.connect(self.save_p)
        v2.addWidget(btn_s);
        layout.addWidget(card2)

        layout.addStretch()
        btn_start = QPushButton("🚀 BẮT ĐẦU LUYỆN TẬP");
        btn_start.setObjectName("Success");
        btn_start.setFixedHeight(70)
        btn_start.clicked.connect(self.go_game)
        layout.addWidget(btn_start)
        self.refresh()

    def refresh(self):
        self.cb_p.clear()
        patients = self.db.get_patients(self.acc_id)
        for p in patients: self.cb_p.addItem(p[1], p[0])

    def save_p(self):
        if self.in_n.text():
            self.db.add_patient(self.acc_id, self.in_n.text(), self.in_a.text())
            self.refresh();
            self.in_n.clear();
            self.in_a.clear()

    def go_profile(self):
        if self.cb_p.currentIndex() != -1: self.ctrl.show_profile(self.cb_p.currentData())

    def go_game(self):
        if self.cb_p.currentIndex() != -1:
            self.ctrl.show_game_selection(self.cb_p.currentData(), self.cb_p.currentText())


# --- BỘ ĐIỀU KHIỂN TRẠNG THÁI (STACK NAVIGATION) ---
class MainController:
    def __init__(self):
        self.db = DatabaseManager()
        self.stack = QStackedWidget();
        self.stack.setFixedSize(550, 800)
        self.stack.setStyleSheet(STYLE_SHEET)
        self.show_login();
        self.stack.show()

    def show_login(self):
        self.login = LoginWindow(self.db, self.show_menu)
        self.stack.addWidget(self.login);
        self.stack.setCurrentWidget(self.login)

    def show_menu(self, acc_id, user):
        self.acc_id = acc_id;
        self.user = user
        self.menu = MainMenu(self.db, acc_id, user, self)
        self.stack.addWidget(self.menu);
        self.stack.setCurrentWidget(self.menu)

    def show_profile(self, p_id):
        # Luôn khởi tạo mới ProfileWindow để lấy dữ liệu DB mới nhất
        self.profile = ProfileWindow(self.db, p_id, lambda: self.stack.setCurrentWidget(self.menu))
        self.stack.addWidget(self.profile);
        self.stack.setCurrentWidget(self.profile)

    def show_game_selection(self, p_id, p_name):
        self.game_sel = GameSelection(self.db, p_id, p_name, lambda: self.stack.setCurrentWidget(self.menu))
        self.stack.addWidget(self.game_sel);
        self.stack.setCurrentWidget(self.game_sel)

if __name__ == "__main__":
    app = QApplication(sys.argv);
    ctrl = MainController();
    sys.exit(app.exec())