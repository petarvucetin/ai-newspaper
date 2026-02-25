import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

DB_PATH = Path(__file__).parent.parent / "data" / "news.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    source_type TEXT,
    identifier TEXT,
    weight REAL DEFAULT 1.0,
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id),
    external_id TEXT,
    title TEXT,
    url TEXT,
    summary TEXT,
    author TEXT,
    published_at DATETIME,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    relevancy_score REAL DEFAULT 0.0,
    display_score REAL DEFAULT 0.0,
    thumbnail_url TEXT,
    upvotes INTEGER DEFAULT 0,
    UNIQUE(source_id, external_id)
);

CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id),
    score INTEGER CHECK(score BETWEEN 1 AND 5),
    rated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS keyword_weights (
    id INTEGER PRIMARY KEY,
    keyword TEXT UNIQUE,
    weight REAL DEFAULT 1.0,
    hits INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_articles_display_score ON articles(display_score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);
"""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.executescript(SCHEMA)
    print(f"Database initialized at {DB_PATH}")


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextmanager
def db_conn() -> Generator[sqlite3.Connection, None, None]:
    con = get_connection()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def seed_keywords(keyword_weights: dict) -> None:
    """Insert keyword weights from config if not already present."""
    with db_conn() as con:
        for kw, weight in keyword_weights.items():
            con.execute(
                "INSERT OR IGNORE INTO keyword_weights (keyword, weight) VALUES (?, ?)",
                (kw.lower(), weight),
            )


def seed_sources(sources_config: dict) -> None:
    """Insert initial sources from config if not already present."""
    with db_conn() as con:
        # Reddit subreddits
        for sub in sources_config.get("reddit", {}).get("subreddits", []):
            name = sub.lstrip("r/")
            con.execute(
                "INSERT OR IGNORE INTO sources (name, source_type, identifier) VALUES (?, ?, ?)",
                (f"r/{name}", "reddit", name),
            )
        # YouTube pinned channels (enabled=1)
        for handle in sources_config.get("youtube", {}).get("channels", []):
            handle = handle.lstrip("@")
            con.execute(
                """INSERT OR IGNORE INTO sources (name, source_type, identifier, enabled)
                   VALUES (?, 'youtube_channel', ?, 1)""",
                (f"@{handle}", f"@{handle}"),
            )
        # YouTube keywords
        for kw in sources_config.get("youtube", {}).get("keywords", []):
            con.execute(
                "INSERT OR IGNORE INTO sources (name, source_type, identifier) VALUES (?, ?, ?)",
                (f"YouTube: {kw}", "youtube", kw),
            )
        # HackerNews
        for kw in sources_config.get("hackernews", {}).get("keywords", []):
            con.execute(
                "INSERT OR IGNORE INTO sources (name, source_type, identifier) VALUES (?, ?, ?)",
                (f"HN: {kw}", "hackernews", kw),
            )


def register_discovered_channel(channel_handle: str, channel_name: str) -> int | None:
    """
    Insert a newly discovered YouTube channel as disabled (pending review).
    Returns the source id if newly inserted, None if it already existed.
    Identifier is the @handle; name is the human-readable channel title.
    """
    handle = channel_handle.lstrip("@")
    identifier = f"@{handle}"
    with db_conn() as con:
        cur = con.execute(
            """INSERT OR IGNORE INTO sources (name, source_type, identifier, enabled)
               VALUES (?, 'youtube_channel', ?, 0)""",
            (channel_name or identifier, identifier),
        )
        if cur.rowcount > 0:
            return cur.lastrowid
    return None


def get_youtube_channels() -> list[sqlite3.Row]:
    """All youtube_channel sources, pinned (enabled) first."""
    with db_conn() as con:
        return con.execute(
            """SELECT * FROM sources WHERE source_type = 'youtube_channel'
               ORDER BY enabled DESC, name""",
        ).fetchall()


# --- Query helpers ---

def get_articles(limit: int = 100, source_type: str | None = None) -> list[sqlite3.Row]:
    with db_conn() as con:
        if source_type == "youtube":
            # Include both keyword-search results and pinned-channel videos
            rows = con.execute(
                """SELECT a.*, s.name AS source_name, s.source_type,
                          (SELECT score FROM ratings WHERE article_id = a.id ORDER BY rated_at DESC LIMIT 1) AS user_rating
                   FROM articles a JOIN sources s ON a.source_id = s.id
                   WHERE s.source_type IN ('youtube', 'youtube_channel')
                   ORDER BY a.display_score DESC, a.fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        elif source_type:
            rows = con.execute(
                """SELECT a.*, s.name AS source_name, s.source_type,
                          (SELECT score FROM ratings WHERE article_id = a.id ORDER BY rated_at DESC LIMIT 1) AS user_rating
                   FROM articles a JOIN sources s ON a.source_id = s.id
                   WHERE s.source_type = ?
                   ORDER BY a.display_score DESC, a.fetched_at DESC LIMIT ?""",
                (source_type, limit),
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT a.*, s.name AS source_name, s.source_type,
                          (SELECT score FROM ratings WHERE article_id = a.id ORDER BY rated_at DESC LIMIT 1) AS user_rating
                   FROM articles a JOIN sources s ON a.source_id = s.id
                   ORDER BY a.display_score DESC, a.fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
    return rows


def get_article_by_id(article_id: int) -> sqlite3.Row | None:
    with db_conn() as con:
        return con.execute(
            "SELECT a.*, s.name AS source_name, s.source_type FROM articles a JOIN sources s ON a.source_id = s.id WHERE a.id = ?",
            (article_id,),
        ).fetchone()


def get_sources() -> list[sqlite3.Row]:
    with db_conn() as con:
        return con.execute("SELECT * FROM sources ORDER BY source_type, name").fetchall()


def get_keyword_weights() -> list[sqlite3.Row]:
    with db_conn() as con:
        return con.execute("SELECT * FROM keyword_weights ORDER BY weight DESC, keyword").fetchall()


def upsert_article(source_id: int, external_id: str, title: str, url: str,
                   summary: str, author: str, published_at, relevancy_score: float,
                   display_score: float, thumbnail_url: str, upvotes: int) -> bool:
    """Returns True if inserted (new), False if already existed."""
    with db_conn() as con:
        cur = con.execute(
            """INSERT OR IGNORE INTO articles
               (source_id, external_id, title, url, summary, author, published_at,
                relevancy_score, display_score, thumbnail_url, upvotes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_id, external_id, title, url, summary, author, published_at,
             relevancy_score, display_score, thumbnail_url, upvotes),
        )
        return cur.rowcount > 0
