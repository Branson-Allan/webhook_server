"""Generic repository: creates/migrates a table from a Resource and upserts Records."""
import json
from datetime import datetime, timezone

from models.database import BaseRepository, Database
from models.resource import Record, Resource

SYSTEM_COLUMNS = (("extra_fields", "TEXT"), ("raw_payload", "TEXT"),
                  ("received_at", "TEXT"), ("updated_at", "TEXT"))
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def q(identifier: str) -> str:
    """Quote an identifier. Names are validated by Resource, so this is safe."""
    return f'"{identifier}"'


class ResourceRepository(BaseRepository):
    def __init__(self, db: Database, resource: Resource):
        super().__init__(db)
        self.resource = resource

    @property
    def _columns(self):
        declared = [(n, f.sql_type) for n, f in self.resource.fields.items()]
        return declared + list(SYSTEM_COLUMNS)

    def create_table(self) -> None:
        """Create the table, and add any columns the schema has gained since."""
        r, table = self.resource, q(self.resource.table)
        defs = ", ".join(f"{q(n)} {t}" + (" PRIMARY KEY" if n == r.key else "")
                         for n, t in self._columns)
        with self.db.transaction() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({defs})")
            existing = {row["name"].lower()
                        for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, sql_type in self._columns:
                if name.lower() not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {q(name)} {sql_type}")

    def save(self, record: Record) -> bool:
        """Insert or update by key. Returns True if a new row was created."""
        r, table = self.resource, q(self.resource.table)
        names = [n for n, _ in self._columns]
        row = record.to_row(datetime.now(timezone.utc).strftime(TIME_FORMAT))
        updates = ", ".join(f"{q(n)}=excluded.{q(n)}"
                            for n in names if n not in (r.key, "received_at"))
        sql = (f"INSERT INTO {table} ({', '.join(q(n) for n in names)}) "
               f"VALUES ({', '.join('?' * len(names))}) "
               f"ON CONFLICT({q(r.key)}) DO UPDATE SET {updates}")
        with self.db.transaction() as conn:
            existed = conn.execute(f"SELECT 1 FROM {table} WHERE {q(r.key)}=?",
                                   (record.key,)).fetchone() is not None
            conn.execute(sql, [row[n] for n in names])
        return not existed

    def find(self, key):
        r = self.resource
        row = self.db.fetch_one(
            f"SELECT * FROM {q(r.table)} WHERE {q(r.key)}=?", (key,))
        if row is None:
            return None
        data = dict(row)
        for name, field in r.fields.items():
            if data.get(name) is not None:
                data[name] = field.from_db(data[name])
        data["extra_fields"] = json.loads(data.get("extra_fields") or "{}")
        return data
