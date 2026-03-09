"""
Global fetch state — tracks progress of the running fetch pipeline
so the admin UI can poll and display live updates. State is persisted
to the database so it survives page refreshes.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


@dataclass
class FetchState:
    status: Literal["idle", "running", "done", "error"] = "idle"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    log: list[str] = field(default_factory=list)
    inserted: int = 0
    skipped: int = 0
    total: int = 0
    error: str = ""

    def reset(self):
        self.status = "running"
        self.started_at = datetime.now(timezone.utc)
        self.finished_at = None
        self.log = []
        self.inserted = 0
        self.skipped = 0
        self.total = 0
        self.error = ""
        self._save()

    def add(self, msg: str):
        self.log.append(msg)
        self._save()

    def finish(self, inserted: int, skipped: int, total: int):
        self.status = "done"
        self.finished_at = datetime.now(timezone.utc)
        self.inserted = inserted
        self.skipped = skipped
        self.total = total
        self._save()

    def fail(self, msg: str):
        self.status = "error"
        self.finished_at = datetime.now(timezone.utc)
        self.error = msg
        self._save()

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "log": self.log,
            "inserted": self.inserted,
            "skipped": self.skipped,
            "total": self.total,
            "error": self.error,
            "elapsed": round(
                (self.finished_at or datetime.now(timezone.utc))
                .timestamp() - (self.started_at or datetime.now(timezone.utc)).timestamp(), 1
            ) if self.started_at else 0,
        }

    def _save(self):
        """Persist state to database."""
        try:
            from app.database import db_conn
            with db_conn() as con:
                con.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    ("fetch_state", json.dumps(self._to_json())),
                )
        except Exception:
            pass  # Don't crash if DB write fails

    def _load(self):
        """Load state from database."""
        try:
            from app.database import db_conn
            with db_conn() as con:
                row = con.execute("SELECT value FROM settings WHERE key = ?", ("fetch_state",)).fetchone()
                if row:
                    data = json.loads(row["value"])
                    self.status = data.get("status", "idle")
                    self.started_at = datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
                    self.finished_at = datetime.fromisoformat(data["finished_at"]) if data.get("finished_at") else None
                    self.log = data.get("log", [])
                    self.inserted = data.get("inserted", 0)
                    self.skipped = data.get("skipped", 0)
                    self.total = data.get("total", 0)
                    self.error = data.get("error", "")
        except Exception:
            pass  # Use defaults if load fails

    def _to_json(self) -> dict:
        """Convert state to JSON-serializable dict."""
        return {
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "log": self.log,
            "inserted": self.inserted,
            "skipped": self.skipped,
            "total": self.total,
            "error": self.error,
        }


# Singleton used across the app
state = FetchState()
# Load persisted state from database on startup
state._load()
