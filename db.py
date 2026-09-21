import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

DB_NAME = "studio.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        # Розкоментуйте ТІЛЬКИ при першому запуску / зміні структури, потім закомментуйте!
        # conn.execute("DROP TABLE IF EXISTS bookings")
        # conn.execute("DROP TABLE IF EXISTS staff")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                hours INTEGER NOT NULL,
                booking_type TEXT NOT NULL,
                instruments TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

    init_roles()
    seed_initial_roles()

def get_bookings_for_period(start_date: str, end_date: str) -> List[Tuple]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("""
            SELECT id, user_id, username, full_name, date, start_time, hours,
                   booking_type, instruments, status
            FROM bookings
            WHERE date BETWEEN ? AND ?
              AND status IN ('confirmed', 'pending')
            ORDER BY date, start_time
        """, (start_date, end_date))
        return cur.fetchall()

def is_range_free(date: str, start_time: str, hours: int) -> bool:
    start_hour = int(start_time.split(":")[0])
    end_hour = start_hour + hours

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("""
            SELECT start_time, hours FROM bookings
            WHERE date = ? AND status IN ('confirmed', 'pending')
        """, (date,))
        for existing_start, existing_hours in cur.fetchall():
            ex_start = int(existing_start.split(":")[0])
            ex_end = ex_start + existing_hours
            if start_hour < ex_end and end_hour > ex_start:
                return False
    return True

def add_booking(user_id: int, username: str, full_name: str,
                date: str, start_time: str, hours: int,
                booking_type: str, instruments: str) -> Optional[int]:
    if not is_range_free(date, start_time, hours):
        return None

    # І репетиція, і запис потребують підтвердження
    status = "pending"

    try:
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.execute("""
                INSERT INTO bookings
                (user_id, username, full_name, date, start_time, hours,
                 booking_type, instruments, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, full_name, date, start_time, hours,
                  booking_type, instruments, status, datetime.now().isoformat()))
            conn.commit()
            return cur.lastrowid
    except Exception:
        return None

def get_user_bookings(user_id: int) -> List[Tuple]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("""
            SELECT id, date, start_time, hours, booking_type, instruments, status
            FROM bookings
            WHERE user_id = ? AND date >= date('now')
              AND status IN ('confirmed', 'pending')
            ORDER BY date, start_time
        """, (user_id,))
        return cur.fetchall()

def get_booking_by_id(booking_id: int) -> Optional[Tuple]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("""
            SELECT id, user_id, username, full_name, date, start_time, hours,
                   booking_type, instruments, status, created_at
            FROM bookings WHERE id = ?
        """, (booking_id,))
        return cur.fetchone()

def cancel_booking(booking_id: int, user_id: int) -> Optional[Tuple]:
    booking = get_booking_by_id(booking_id)
    if not booking or booking[1] != user_id:
        return None
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND user_id = ?",
            (booking_id, user_id)
        )
        conn.commit()
        if cur.rowcount > 0:
            return booking
    return None

def admin_cancel_booking(booking_id: int) -> Optional[Tuple]:
    booking = get_booking_by_id(booking_id)
    if not booking:
        return None
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ?",
            (booking_id,)
        )
        conn.commit()
        if cur.rowcount > 0:
            return booking
    return None

def confirm_booking(booking_id: int) -> Optional[Tuple]:
    booking = get_booking_by_id(booking_id)
    if not booking or booking[9] != "pending":
        return None
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "UPDATE bookings SET status = 'confirmed' WHERE id = ?",
            (booking_id,)
        )
        conn.commit()
        if cur.rowcount > 0:
            return get_booking_by_id(booking_id)
    return None

def reject_booking(booking_id: int) -> Optional[Tuple]:
    booking = get_booking_by_id(booking_id)
    if not booking or booking[9] != "pending":
        return None
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "UPDATE bookings SET status = 'rejected' WHERE id = ?",
            (booking_id,)
        )
        conn.commit()
        if cur.rowcount > 0:
            return booking
    return None

# ====================== РОЛІ ======================

def init_roles():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                added_by INTEGER,
                added_at TEXT,
                notifications INTEGER DEFAULT 1
            )
        """)
        conn.commit()

def seed_initial_roles():
    from config import INITIAL_MANAGER_IDS

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM staff")
        if cur.fetchone()[0] > 0:
            return

        now = datetime.now().isoformat()
        for uid in INITIAL_MANAGER_IDS:
            conn.execute(
                "INSERT OR IGNORE INTO staff (user_id, role, added_by, added_at, notifications) VALUES (?, 'manager', ?, ?, 1)",
                (uid, uid, now)
            )
        conn.commit()

def get_user_role(user_id: int) -> Optional[str]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("SELECT role FROM staff WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None

def get_staff_by_role(role: str) -> List[int]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("SELECT user_id FROM staff WHERE role = ?", (role,))
        return [row[0] for row in cur.fetchall()]

def add_staff(user_id: int, role: str, added_by: int) -> bool:
    if role not in ("admin", "sound_engineer", "manager"):
        return False
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO staff (user_id, role, added_by, added_at, notifications) VALUES (?, ?, ?, ?, 1)",
                (user_id, role, added_by, datetime.now().isoformat())
            )
            conn.commit()
        return True
    except Exception:
        return False

def remove_staff(user_id: int) -> bool:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("DELETE FROM staff WHERE user_id = ?", (user_id,))
        conn.commit()
        return cur.rowcount > 0

def get_all_staff() -> List[Tuple]:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute("SELECT user_id, role FROM staff ORDER BY role, user_id")
        return cur.fetchall()

def set_notifications(user_id: int, enabled: bool) -> bool:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "UPDATE staff SET notifications = ? WHERE user_id = ?",
            (1 if enabled else 0, user_id)
        )
        conn.commit()
        return cur.rowcount > 0

def get_notifications(user_id: int) -> bool:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "SELECT notifications FROM staff WHERE user_id = ?",
            (user_id,)
        )
        row = cur.fetchone()
        return bool(row[0]) if row else True