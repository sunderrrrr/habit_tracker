import sqlite3
from datetime import datetime, date
from typing import List, Optional, Tuple
import logging
from exceptions import DBError
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db: str = "habits.db"):
        self.db = db
        self.migrations_up()
    def connect(self):
        try:
            conn = sqlite3.connect(self.db)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            raise DBError(f"Database connect error: {e}")
    def migrations_up(self):
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS habits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_completed DATE,
                    current_streak INTEGER DEFAULT 0,
                    total_completions INTEGER DEFAULT 0,
                    UNIQUE(user_id, name)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS completions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    habit_id INTEGER NOT NULL,
                    completion_date DATE NOT NULL,
                    FOREIGN KEY (habit_id) REFERENCES habits (id) ON DELETE CASCADE,
                    UNIQUE(habit_id, completion_date)
                )
            """)
            conn.commit()
            logger.info("DB migrations successful up")
        except Exception as e:
            raise DBError(f"DB migrations up error: {e}")        
    def add_habit(self, user_id: int, name: str) -> int:
        name = name.strip()
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM habits WHERE user_id = ? AND name = ?",
                (user_id, name)
            )
            if cursor.fetchone():
                raise DBError("Привычка с таким названием уже существует")
            cursor.execute(
                """
                INSERT INTO habits (user_id, name, created_at) 
                VALUES (?, ?, ?)
                """, (user_id, name, datetime.now())
            )
            id = cursor.lastrowid
            conn.commit()
            return id
        except Exception as e:
            raise DBError(f"DBError while adding new habit: {e}")