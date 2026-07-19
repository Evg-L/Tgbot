import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Tuple


class Database:
    def __init__(self, db_name: str):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_tables()

    def _init_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                stars INTEGER DEFAULT 2,
                referrer_id INTEGER,
                join_date TEXT,
                last_active TEXT
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                referral_date TEXT,
                rewarded BOOLEAN DEFAULT FALSE
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                video_id TEXT,
                purchase_date TEXT,
                file_path TEXT
            )
        """)

        self.conn.commit()

    def add_user(self, user_id: int, username: str, first_name: str):
        now = datetime.now().isoformat()
        self.cursor.execute("""
            INSERT OR IGNORE INTO users 
            (user_id, username, first_name, join_date, last_active, stars)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, first_name, now, now, 2))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_user(self, user_id: int) -> Optional[Dict]:
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row:
            columns = [desc[0] for desc in self.cursor.description]
            return dict(zip(columns, row))
        return None

    def add_stars(self, user_id: int, amount: int) -> int:
        self.cursor.execute(
            "UPDATE users SET stars = stars + ? WHERE user_id = ?",
            (amount, user_id)
        )
        self.conn.commit()
        self.cursor.execute("SELECT stars FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()[0]

    def remove_stars(self, user_id: int, amount: int) -> bool:
        self.cursor.execute("SELECT stars FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if not row or row[0] < amount:
            return False
        self.cursor.execute(
            "UPDATE users SET stars = stars - ? WHERE user_id = ?",
            (amount, user_id)
        )
        self.conn.commit()
        return True

    def set_referrer(self, user_id: int, referrer_id: int) -> bool:
        user = self.get_user(user_id)
        if not user or user["referrer_id"] is not None or user_id == referrer_id:
            return False

        self.cursor.execute(
            "UPDATE users SET referrer_id = ? WHERE user_id = ?",
            (referrer_id, user_id)
        )
        self.conn.commit()

        now = datetime.now().isoformat()
        self.cursor.execute("""
            INSERT OR IGNORE INTO referrals (referrer_id, referred_id, referral_date)
            VALUES (?, ?, ?)
        """, (referrer_id, user_id, now))
        self.conn.commit()

        self.cursor.execute(
            "SELECT rewarded FROM referrals WHERE referred_id = ?", (user_id,)
        )
        row = self.cursor.fetchone()
        if row and not row[0]:
            self.add_stars(referrer_id, 2)
            self.cursor.execute(
                "UPDATE referrals SET rewarded = TRUE WHERE referred_id = ?",
                (user_id,)
            )
            self.conn.commit()
        return True

    def get_referral_count(self, user_id: int) -> int:
        self.cursor.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
            (user_id,)
        )
        return self.cursor.fetchone()[0]

    def get_purchased_videos(self, user_id: int) -> List[Tuple]:
        self.cursor.execute(
            "SELECT video_id, file_path, purchase_date FROM purchases WHERE user_id = ? ORDER BY purchase_date DESC",
            (user_id,)
        )
        return self.cursor.fetchall()

    def add_purchase(self, user_id: int, video_id: str, file_path: str):
        now = datetime.now().isoformat()
        self.cursor.execute("""
            INSERT INTO purchases (user_id, video_id, file_path, purchase_date)
            VALUES (?, ?, ?, ?)
        """, (user_id, video_id, file_path, now))
        self.conn.commit()

    def close(self):
        self.conn.close()