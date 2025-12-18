import sqlite3
from datetime import datetime, date
from typing import List, Optional, Tuple
import logging
from exceptions import DBError

logger = logging.getLogger(__name__)


class Database:
    """
    Класс для работы с базой данных привычек

    Обеспечивает создание, чтение, обновление и удаление привычек,
    а также отслеживание их выполнения

    :ivar db: Путь к файлу базы данных
    :type db: str
    """

    def __init__(self, db: str = "habits.db"):
        """
        Конструктор класса

        :param db: Путь к файлу базы данных (по умолчанию "habits.db")
        :type db: str
        """

        self.db = db
        self.migrations_up()

    def connect(self) -> sqlite3.Connection:
        """
        Установка соединения с базой данных

        :returns: Объект соединения с БД
        :type: sqlite3.Connection
        :raises DBError: Если произошла ошибка при подключении к БД
        """
        try:
            conn = sqlite3.connect(self.db)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            raise DBError(f"Database connect error: {e}")

    def migrations_up(self) -> None:
        """
        Применение миграций базы данных

        :raises DBError: Если произошла ошибка при применении миграций
        """

        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                """
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
            """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS completions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    habit_id INTEGER NOT NULL,
                    completion_date DATE NOT NULL,
                    FOREIGN KEY (habit_id) REFERENCES habits (id) ON DELETE CASCADE,
                    UNIQUE(habit_id, completion_date)
                )
            """
            )
            conn.commit()
            logger.info("DB migrations successful up")
        except Exception as e:
            logger.error(f"DB migrations up error: {e}")
            raise DBError(f"DB migrations up error: {e}")

    def add_habit(self, uid: int, name: str) -> int:
        """
        Добавление новой привычки для пользователя

        :param uid: ID пользователя
        :type uid: int
        :param name: Название привычки
        :type name: str
        :returns: ID созданной привычки
        :type: int
        :raises DBError: Если привычка с таким названием уже существует или произошла ошибка БД
        """

        name = name.strip()
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM habits WHERE user_id = ? AND name = ?",
                (uid, name),
            )
            if cursor.fetchone():
                raise DBError("Habit with this name already exists")
            cursor.execute(
                """
                INSERT INTO habits (user_id, name, created_at) 
                VALUES (?, ?, ?)
                """,
                (uid, name, datetime.now()),
            )
            id = cursor.lastrowid
            conn.commit()
            return id
        except Exception as e:
            logger.error(f"Error while adding new habit: {e}")
            raise DBError(f"Error while adding new habit: {e}")

    def get_user_habits(self, user_id: int) -> List[dict]:
        """
        Получение списка привычек пользователя

        :param user_id: ID пользователя
        :type user_id: int
        :returns: Список привычек пользователя
        :type: List[dict]
        :raises DBError: Если произошла ошибка при получении привычек
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    id, name, created_at, last_completed,
                    current_streak, total_completions
                FROM habits 
                WHERE user_id = ? 
                ORDER BY current_streak DESC, name
                """,
                (user_id,),
            )
            habits = []
            for row in cursor.fetchall():
                habits.append(dict(row))
            return habits
        except Exception as e:
            logger.error(f"Get habits error: {e}")
            raise DBError(f"Get habits error: {e}")

    def delete_habit(self, uid: int, hid: int) -> bool:
        """
        Удаление привычки пользователя

        :param uid: ID пользователя
        :type uid: int
        :param hid: ID привычки
        :type hid: int
        :returns: True если привычка успешно удалена
        :type: bool
        :raises DBError: Если привычка не существует или произошла ошибка БД
        """

        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM habits WHERE id = ? AND user_id = ?",
                (hid, uid),
            )
            exist = cursor.fetchone()
            if not exist:
                raise DBError(f"Habit with id:{hid} don't exist")
            cursor.execute(
                "DELETE FROM habits WHERE id = ? AND user_id = ?", (hid, uid)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Delet habit error: {e}")
            raise DBError(f"Delete habit error: {e}")

    def complete_habit(self, hid: int, uid: int) -> dict:
        """
        Отметка выполнения привычки

        Обновляет статистику привычки: текущую серию, общее количество выполнений,
        дату последнего выполнения

        :param hid: ID привычки
        :type hid: int
        :param uid: ID пользователя
        :type uid: int
        :returns: Обновленные данные привычки
        :type: dict
        :raises DBError: Если привычка не найдена, уже выполнена сегодня или произошла ошибка БД
        """

        try:
            conn = self.connect()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT * FROM habits WHERE id = ? AND user_id = ?",
                    (hid, uid),
                )
                habit = cursor.fetchone()
            except Exception as e:
                raise DBError(f"Habit not found error: {e}")

            last_completed = habit["last_completed"]
            today = datetime.now().date().isoformat()
            if last_completed == today:
                raise DBError("Habit is completed today")

            if last_completed:
                last_date = datetime.strptime(last_completed, "%Y-%m-%d").date()
                days_diff = (datetime.now().date() - last_date).days
                if days_diff == 1:
                    new_streak = habit["current_streak"] + 1
                else:
                    new_streak = 1
            else:
                new_streak = 1

            try:
                cursor.execute(
                    """
                UPDATE habits 
                SET last_completed = ?,
                    current_streak = ?,
                    total_completions = total_completions + 1
                WHERE id = ? AND user_id = ?
                """,
                    (today, new_streak, hid, uid),
                )
            except Exception as e:
                raise DBError(f"Habit update error: {e}")
            conn.commit()
            try:
                cursor.execute(
                    "SELECT * FROM habits WHERE id = ? AND user_id = ?",
                    (hid, uid),
                )
                updated_habit = cursor.fetchone()

                return dict(updated_habit)
            except Exception as e:
                raise DBError(f"New habit get error: {e}")
        except Exception as e:
            logger.error(f"Habit complete error: {e}")
            raise DBError(f"Habit complete error: {e}")
