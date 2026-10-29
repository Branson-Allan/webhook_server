"""SQLite access and the repository base class."""
import sqlite3
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager


class Database:
    def __init__(self, path: str):
        self.path = path
        self._write_lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def transaction(self):
        """Serialised write transaction: commits on success, rolls back on error."""
        with self._write_lock:
            conn = self._connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def fetch_one(self, sql: str, params=()):
        conn = self._connect()
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()


class BaseRepository(ABC):
    def __init__(self, db: Database):
        self.db = db

    @abstractmethod
    def create_table(self) -> None: ...
