"""
Global fetch state — tracks progress of the running fetch pipeline
so the admin UI can poll and display live updates.
"""
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

    def add(self, msg: str):
        self.log.append(msg)

    def finish(self, inserted: int, skipped: int, total: int):
        self.status = "done"
        self.finished_at = datetime.now(timezone.utc)
        self.inserted = inserted
        self.skipped = skipped
        self.total = total

    def fail(self, msg: str):
        self.status = "error"
        self.finished_at = datetime.now(timezone.utc)
        self.error = msg

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


# Singleton used across the app
state = FetchState()
