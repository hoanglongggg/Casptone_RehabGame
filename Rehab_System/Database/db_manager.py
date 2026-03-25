import sqlite3
import os


class DatabaseManager:
    def __init__(self):
        if not os.path.exists("Database"):
            os.makedirs("Database")
        self.conn = sqlite3.connect("Database/rehab_system.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Bảng tài khoản bác sĩ
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS accounts 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)''')

        # Bảng hồ sơ bệnh nhân
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            name TEXT NOT NULL,
            age INTEGER,
            dob TEXT, disease TEXT, condition TEXT, note TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts (id))''')

        # Bảng lịch sử tập luyện
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            game_name TEXT,
            reps INTEGER,
            avg_flexion REAL,
            duration REAL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients (id))''')
        self.conn.commit()

    def login(self, u, p):
        self.cursor.execute("SELECT id FROM accounts WHERE username=? AND password=?", (u, p))
        return self.cursor.fetchone()

    def add_account(self, u, p):
        try:
            self.cursor.execute("INSERT INTO accounts (username, password) VALUES (?, ?)", (u, p))
            self.conn.commit()
            return True
        except:
            return False

    def add_patient(self, acc_id, name, age):
        self.cursor.execute("INSERT INTO patients (account_id, name, age) VALUES (?, ?, ?)", (acc_id, name, age))
        self.conn.commit()

    def get_patients(self, acc_id):
        self.cursor.execute("SELECT id, name, age FROM patients WHERE account_id=?", (acc_id,))
        return self.cursor.fetchall()

    def get_patient_detail(self, p_id):
        self.cursor.execute("SELECT * FROM patients WHERE id=?", (p_id,))
        return self.cursor.fetchone()

    def update_patient(self, p_id, disease, cond, note):
        self.cursor.execute("UPDATE patients SET disease=?, condition=?, note=? WHERE id=?",
                            (disease, cond, note, p_id))
        self.conn.commit()

    def get_sessions(self, p_id):
        self.cursor.execute(
            "SELECT date, game_name, reps, ROUND(avg_flexion, 2), duration FROM sessions WHERE patient_id=? ORDER BY date DESC",
            (p_id,))
        return self.cursor.fetchall()

    def add_session(self, patient_id, game_name, reps, avg_flexion, duration):
        """
        Lưu 1 lần tập luyện (session) vào bảng `sessions`.
        """
        self.cursor.execute(
            "INSERT INTO sessions (patient_id, game_name, reps, avg_flexion, duration) VALUES (?, ?, ?, ?, ?)",
            (patient_id, game_name, int(reps), float(avg_flexion), float(duration))
        )
        self.conn.commit()