import sys
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
from Database.db_manager import DatabaseManager

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


# --- MÀN HÌNH CHỌN GAME ---
class GameSelection(QWidget):
    def __init__(self, patient_name, on_back):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        btn_back = QPushButton("← Quay lại Menu");
        btn_back.setFixedWidth(150)
        btn_back.clicked.connect(on_back);
        layout.addWidget(btn_back)

        title = QLabel(f"BÀI TẬP CHO: {patient_name.upper()}")
        title.setObjectName("Header");
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(20)

        # Danh sách game
        games = [
            ("🍎 Game Hái Táo", "apple_game"),
            ("🏎️ Game Đua Xe", "racing_game"),
            ("💪 Bài tập Co Duỗi", "flex_exercise")
        ]

        for name, key in games:
            btn = QPushButton(name)
            btn.setFixedHeight(80)
            btn.setStyleSheet("background-color: #2C2C2C; font-size: 18px; text-align: left; padding-left: 30px;")
            # FIX LỖI CHỈ MỞ MỘT GAME: Sử dụng n=name để capture giá trị hiện tại
            btn.clicked.connect(lambda checked=False, n=name: self.start_game(n))
            layout.addWidget(btn)

        layout.addStretch()

    def start_game(self, game_name):
        QMessageBox.information(self, "Khởi chạy",
                                f"Đang chuẩn bị dữ liệu cho: {game_name}\nHệ thống đang mở camera...")


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
        if self.cb_p.currentIndex() != -1: self.ctrl.show_game_selection(self.cb_p.currentText())


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

    def show_game_selection(self, p_name):
        self.game_sel = GameSelection(p_name, lambda: self.stack.setCurrentWidget(self.menu))
        self.stack.addWidget(self.game_sel);
        self.stack.setCurrentWidget(self.game_sel)

if __name__ == "__main__":
    app = QApplication(sys.argv);
    ctrl = MainController();
    sys.exit(app.exec())