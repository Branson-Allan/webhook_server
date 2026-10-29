"""Persistence for issued access tokens (only SHA-256 hashes are stored)."""
from models.database import BaseRepository


class TokenRepository(BaseRepository):
    def create_table(self) -> None:
        with self.db.transaction() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS tokens ("
                         "token_hash TEXT PRIMARY KEY, expires_at REAL)")

    def add(self, token_hash: str, expires_at: float, now: float) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM tokens WHERE expires_at < ?", (now,))
            conn.execute("INSERT INTO tokens VALUES (?, ?)", (token_hash, expires_at))

    def expiry_of(self, token_hash: str):
        row = self.db.fetch_one("SELECT expires_at FROM tokens WHERE token_hash=?",
                                (token_hash,))
        return row["expires_at"] if row else None
