# database.py
# -----------
# Stores download history using SQLite (built into Python -- no extra
# install needed). Each row is one completed/attempted download.

import sqlite3
import os
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")


class HistoryDatabase:
    # Wraps all SQLite access for the download history feature.

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT, url TEXT, platform TEXT, "
            "date_added TEXT, filepath TEXT, status TEXT)"
        )
        conn.commit()
        conn.close()

    def add_entry(self, title, url, platform, filepath, status):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO history (title, url, platform, date_added, filepath, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, url, platform, str(datetime.datetime.now()), filepath, status),
        )
        conn.commit()
        entry_id = cur.lastrowid
        conn.close()
        return entry_id

    def update_status(self, entry_id, status, filepath=None):
        conn = self._connect()
        cur = conn.cursor()
        if filepath is not None:
            cur.execute(
                "UPDATE history SET status = ?, filepath = ? WHERE id = ?",
                (status, filepath, entry_id),
            )
        else:
            cur.execute("UPDATE history SET status = ? WHERE id = ?", (status, entry_id))
        conn.commit()
        conn.close()

    def get_all(self):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT id, title, url, platform, date_added, filepath, status FROM history ORDER BY id DESC")
        rows = cur.fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def search(self, keyword):
        conn = self._connect()
        cur = conn.cursor()
        like_term = "%{}%".format(keyword)
        cur.execute(
            "SELECT id, title, url, platform, date_added, filepath, status FROM history "
            "WHERE title LIKE ? OR platform LIKE ? ORDER BY id DESC",
            (like_term, like_term),
        )
        rows = cur.fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def delete_entry(self, entry_id):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM history WHERE id = ?", (entry_id,))
        conn.commit()
        conn.close()

    def clear_all(self):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM history")
        conn.commit()
        conn.close()

    def _row_to_dict(self, row):
        return {
            "id": row[0],
            "title": row[1],
            "url": row[2],
            "platform": row[3],
            "date_added": row[4],
            "filepath": row[5],
            "status": row[6],
        }
