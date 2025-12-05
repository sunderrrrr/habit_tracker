import builtins
from unittest.mock import Mock, patch, MagicMock
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) # Указание пути к корню проекта для импорта из директорий на уровень выше
from db import Database
from exceptions import DBError

def test_db_init_success():
    mock_connect = Mock()
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    with patch('sqlite3.connect', mock_connect):
        db = Database(":memory:")
        mock_connect.assert_called_once()

def test_db_init_fail():
    db = Database(":memory:")
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.execute.side_effect = DBError()
    db.connect = Mock(return_value=mock_conn)
    with pytest.raises(DBError):
        db.migrations_up()
    
def test_add_habit_success():
    db = Database(":memory:")
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None 
    mock_cursor.lastrowid = 1
    db.connect = Mock(return_value=mock_conn)
    with patch('db.datetime') as mock_time:
        mock_now = Mock()
        mock_time.now.return_value = mock_now
        hid = db.add_habit(12345, "qwerty")
    assert mock_cursor.execute.call_count >= 2 
    mock_conn.commit.assert_called_once()
    assert hid == 1
