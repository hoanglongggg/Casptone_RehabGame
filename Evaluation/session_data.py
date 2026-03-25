import sqlite3
import os


class DatabaseManager:
    def __init__(self):
        # Tạo thư mục Database nếu chưa có
        if not os.path.exists("Database"):
            os.makedirs("Database")

        self.conn = sqlite3.connect("Database/rehab_system.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Bảng bệnh nhân
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER,
                condition TEXT
            )
        ''')
        # Bảng lịch sử tập
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                game_name TEXT,
                reps INTEGER,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
        ''')
        self.conn.commit()

    def add_patient(self, name, age):
        self.cursor.execute("INSERT INTO patients (name, age) VALUES (?, ?)", (name, age))
        self.conn.row_factory = sqlite3.Row
        self.conn.commit()

    def get_patients(self):
        self.cursor.execute("SELECT * FROM patients")
        return self.cursor.fetchall()