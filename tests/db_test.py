import builtins
from unittest.mock import Mock, patch
import pytest
import sys
import os
import sqlite3
from datetime import date, datetime

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)  # Указание пути к корню проекта для импорта из директорий на уровень выше
from db import Database
from exceptions import DBError


def test_db_init_success():
    """
    Позитивный тест на инициализацию БД
    """

    mock_connect = Mock()
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    with patch("sqlite3.connect", mock_connect):
        db = Database(":memory:")
        mock_connect.assert_called_once()


def test_db_init_fail():
    """
    Негативный тест на инициализацию БД
    """

    db = Database(":memory:")
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.execute.side_effect = DBError()
    db.connect = Mock(return_value=mock_conn)
    with pytest.raises(DBError):
        db.migrations_up()


def test_add_habit_success():
    """
    Позитивный тест на добавление привычки
    """

    db = Database(":memory:")
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    mock_cursor.lastrowid = 1
    db.connect = Mock(return_value=mock_conn)
    with patch("db.datetime") as mock_time:
        mock_now = Mock()
        mock_time.now.return_value = mock_now
        hid = db.add_habit(12345, "qwerty")
    assert mock_cursor.execute.call_count >= 2
    mock_conn.commit.assert_called_once()
    assert hid == 1


def test_add_habit_exist_negative():
    """
    Негативный тест на добавление уже существующей привычки
    """

    db = Database(":memory:")
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [1]
    db.connect = Mock(return_value=mock_conn)
    with pytest.raises(DBError, match="Habit with this name already exists"):
        db.add_habit(12345, "qwerty")


def test_get_habbit_sucess():
    """
    Успешный тест получения списка привычек
    """

    db = Database(":memory:")
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor

    mock_rows = [
        {
            "id": 1,
            "name": "qwerty1",
            "current_streak": 4,
        },
        {
            "id": 2,
            "name": "qwerty2",
            "current_streak": 3,
        },
    ]
    mock_cursor.fetchall.return_value = mock_rows
    db.connect = Mock(return_value=mock_conn)

    habits = db.get_user_habits(12345)
    mock_cursor.execute.assert_called_once()
    assert len(habits) == 2
    assert habits[0]["name"] == "qwerty1"


def test_delete_habit_sucess():
    """
    Положительный тест удаления привычки
    """

    db = Database(":memory:")
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [1]
    db.connect = Mock(return_value=mock_conn)

    res = db.delete_habit(12345, 1)
    mock_cursor.execute.assert_any_call(
        "SELECT id FROM habits WHERE id = ? AND user_id = ?", (1, 12345)
    )
    mock_cursor.execute.assert_any_call(
        "DELETE FROM habits WHERE id = ? AND user_id = ?", (1, 12345)
    )
    mock_conn.commit.assert_called_once()

    assert res is True
    assert mock_cursor.execute.call_count == 2


def test_delete_habit_not_found():
    """
    Тест на удаление несуществующей привычки
    """

    db = Database(":memory:")
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    db.connect = Mock(return_value=mock_conn)

    with pytest.raises(DBError, match="Habit with id:1 don't exist"):
        db.delete_habit(12345, 1)


def test_complete_habit_success():
    """
    Положительный тест на выполнение привычки
    """
    db = Database(":memory:")
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor

    habit_data = {
        "id": 1,
        "user_id": 12345,
        "last_completed": "2023-01-01",
        "current_streak": 5,
        "total_completions": 10,
    }
    mock_cursor.fetchone.side_effect = [
        sqlite3.Row(habit_data),
        sqlite3.Row(habit_data),
    ]

    db.connect = Mock(return_value=mock_conn)

    with patch("db.datetime") as mock_datetime:
        mock_now = Mock()
        mock_now.date.return_value = date(2023, 1, 3)
        mock_datetime.now.return_value = mock_now
        mock_datetime.strptime.return_value = datetime(2023, 1, 1)

        result = db.complete_habit(1, 12345)

    assert mock_cursor.execute.call_count == 3
    mock_conn.commit.assert_called_once()
    assert isinstance(result, dict)


def test_habit_already_complete():
    """
    Тест на выполнение уже выполненной привычки
    """
    db = Database(":memory:")
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor

    habit_data = {
        "id": 1,
        "user_id": 12345,
        "last_completed": "2023-01-03",
        "current_streak": 5,
    }
    mock_cursor.fetchone.return_value = sqlite3.Row(habit_data)
    db.connect = Mock(return_value=mock_conn)

    with patch("db.datetime") as mock_datetime:
        mock_now = Mock()
        mock_now.date.return_value = date(2025, 12, 17)
        mock_datetime.now.return_value = mock_now

        with pytest.raises(DBError, match="Habit is completed today"):
            db.complete_habit(1, 12345)
