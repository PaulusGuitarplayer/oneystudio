import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

DB_NAME = "studio.db"

def get_booking_by_id(booking_id: int) -> tuple | None:
    """Возвращает данные брони по ID"""
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("""
            SELECT id, user_id, username, full_name, date, time_slot
            FROM bookings
            WHERE id = ?
        """, (booking_id,))
        return cur.fetchone()

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                date TEXT NOT NULL,          -- YYYY-MM-DD
                time_slot TEXT NOT NULL,    -- HH:MM
                created_at TEXT NOT NULL,
                UNIQUE(date, time_slot)
            )
        """)
        conn.commit()

def get_bookings_for_period(start_date: str, end_date: str) -> List[Tuple]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("""
            SELECT date, time_slot, user_id, username, full_name
            FROM bookings
            WHERE date BETWEEN ? AND ?
            ORDER BY date, time_slot
        """, (start_date, end_date))
        return cur.fetchall()

def is_slot_free(date: str, time_slot: str) -> bool:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "SELECT 1 FROM bookings WHERE date = ? AND time_slot = ?",
            (date, time_slot)
        )
        return cur.fetchone() is None

def are_slots_free(date: str, start_time: str, hours: int) -> bool:
    """Проверяет, свободны ли hours часов начиная с start_time"""
    start_hour = int(start_time.split(":")[0])
    for i in range(hours):
        slot = f"{start_hour + i:02d}:00"
        if not is_slot_free(date, slot):
            return False
    return True

def add_booking(user_id: int, username: str, full_name: str,
                date: str, start_time: str, hours: int = 1) -> bool:
    """Бронирует несколько часов подряд"""
    if not are_slots_free(date, start_time, hours):
        return False

    start_hour = int(start_time.split(":")[0])
    try:
        with sqlite3.connect(DB_NAME) as conn:
            for i in range(hours):
                slot = f"{start_hour + i:02d}:00"
                conn.execute("""
                    INSERT INTO bookings (user_id, username, full_name, date, time_slot, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, username, full_name, date, slot,
                      datetime.now().isoformat()))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def get_user_bookings(user_id: int) -> List[Tuple]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("""
            SELECT id, date, time_slot
            FROM bookings
            WHERE user_id = ? AND date >= date('now')
            ORDER BY date, time_slot
        """, (user_id,))
        return cur.fetchall()

def cancel_booking(booking_id: int, user_id: int) -> tuple | None:
    """Удаляет бронь и возвращает её данные, если удаление успешно"""
    booking = get_booking_by_id(booking_id)
    if not booking:
        return None
    
    # Проверяем, что бронь принадлежит этому пользователю
    if booking[1] != user_id:
        return None

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "DELETE FROM bookings WHERE id = ? AND user_id = ?",
            (booking_id, user_id)
        )
        conn.commit()
        if cur.rowcount > 0:
            return booking
    return None