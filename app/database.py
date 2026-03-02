import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

DB_PATH = Path(os.environ.get("NEWS_DB_PATH", str(Path(__file__).parent.parent / "data" / "news.db")))

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
    thumbnail_url TEXT, num_comments INTEGER DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    purpose TEXT,
    called_at DATETIME DEFAULT CURRENT_TIMESTAMP
);


CREATE INDEX IF NOT EXISTS idx_articles_display_score ON articles(display_score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_fetched_at ON articles(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);

-- dismissed column added in v2 (idempotent via ALTER TABLE guard)

"""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.executescript(SCHEMA)
        # Idempotent migrations
        cols = {row[1] for row in con.execute("PRAGMA table_info(articles)")}
        if "dismissed" not in cols:
            con.execute("ALTER TABLE articles ADD COLUMN dismissed BOOLEAN DEFAULT 0")
        if "dismissed_at" not in cols:
            con.execute("ALTER TABLE articles ADD COLUMN dismissed_at DATETIME")
        if "auto_dismissed" not in cols:
            con.execute("ALTER TABLE articles ADD COLUMN auto_dismissed BOOLEAN DEFAULT 0")
        if "num_comments" not in cols:
            con.execute("ALTER TABLE articles ADD COLUMN num_comments INTEGER DEFAULT 0")
        src_cols = {row[1] for row in con.execute("PRAGMA table_info(sources)")}
        if "blocked" not in src_cols:
            con.execute("ALTER TABLE sources ADD COLUMN blocked BOOLEAN DEFAULT 0")
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
    Skips channels that have been blocked (removed by admin).
    """
    handle = channel_handle.lstrip("@")
    identifier = f"@{handle}"
    with db_conn() as con:
        # Don't re-add channels that were blocked by admin
        blocked = con.execute(
            "SELECT 1 FROM sources WHERE identifier = ? AND blocked = 1", (identifier,)
        ).fetchone()
        if blocked:
            return None
        cur = con.execute(
            """INSERT OR IGNORE INTO sources (name, source_type, identifier, enabled)
               VALUES (?, 'youtube_channel', ?, 0)""",
            (channel_name or identifier, identifier),
        )
        if cur.rowcount > 0:
            return cur.lastrowid
    return None


def add_youtube_channel(handle: str) -> bool:
    """Add a pinned YouTube channel. Returns True if newly inserted. Refuses blocked channels."""
    handle = handle.strip().lstrip("@")
    identifier = f"@{handle}"
    with db_conn() as con:
        blocked = con.execute(
            "SELECT 1 FROM sources WHERE identifier = ? AND blocked = 1", (identifier,)
        ).fetchone()
        if blocked:
            return False
        cur = con.execute(
            """INSERT OR IGNORE INTO sources (name, source_type, identifier, enabled)
               VALUES (?, 'youtube_channel', ?, 1)""",
            (identifier, identifier),
        )
        return cur.rowcount > 0


def add_reddit_subreddit(subreddit: str) -> bool:
    """Add a Reddit subreddit source. Returns True if newly inserted. Refuses blocked."""
    name = subreddit.strip().lstrip("r/").lstrip("/")
    with db_conn() as con:
        blocked = con.execute(
            "SELECT 1 FROM sources WHERE identifier = ? AND source_type = 'reddit' AND blocked = 1",
            (name,),
        ).fetchone()
        if blocked:
            return False
        cur = con.execute(
            """INSERT OR IGNORE INTO sources (name, source_type, identifier, enabled)
               VALUES (?, 'reddit', ?, 1)""",
            (f"r/{name}", name),
        )
        return cur.rowcount > 0


def get_reddit_sources() -> list[sqlite3.Row]:
    """All Reddit subreddit sources. Excludes blocked."""
    with db_conn() as con:
        return con.execute(
            """SELECT * FROM sources WHERE source_type = 'reddit'
               AND COALESCE(blocked, 0) = 0
               ORDER BY enabled DESC, name""",
        ).fetchall()


def get_all_youtube_channel_identifiers() -> set[str]:
    """All youtube_channel identifiers including blocked (for dedup during fetch)."""
    with db_conn() as con:
        rows = con.execute(
            "SELECT identifier FROM sources WHERE source_type = 'youtube_channel'"
        ).fetchall()
        return {row["identifier"] for row in rows}


def get_youtube_channels() -> list[sqlite3.Row]:
    """All youtube_channel sources, pinned (enabled) first. Excludes blocked."""
    with db_conn() as con:
        return con.execute(
            """SELECT * FROM sources WHERE source_type = 'youtube_channel'
               AND COALESCE(blocked, 0) = 0
               ORDER BY enabled DESC, name""",
        ).fetchall()


# --- Query helpers ---

def get_articles(limit: int = 100, source_type: str | None = None) -> list[sqlite3.Row]:
    with db_conn() as con:
        if source_type == "youtube":
            rows = con.execute(
                """SELECT a.*, s.name AS source_name, s.source_type,
                          (SELECT score FROM ratings WHERE article_id = a.id ORDER BY rated_at DESC LIMIT 1) AS user_rating
                   FROM articles a JOIN sources s ON a.source_id = s.id
                   WHERE s.source_type IN ('youtube', 'youtube_channel')
                     AND COALESCE(a.dismissed, 0) = 0
                   ORDER BY a.upvotes DESC, a.fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        elif source_type == "reddit":
            rows = con.execute(
                """SELECT a.*, s.name AS source_name, s.source_type,
                          (SELECT score FROM ratings WHERE article_id = a.id ORDER BY rated_at DESC LIMIT 1) AS user_rating
                   FROM articles a JOIN sources s ON a.source_id = s.id
                   WHERE s.source_type = 'reddit' AND COALESCE(a.dismissed, 0) = 0
                   ORDER BY a.upvotes DESC, a.fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        elif source_type:
            rows = con.execute(
                """SELECT a.*, s.name AS source_name, s.source_type,
                          (SELECT score FROM ratings WHERE article_id = a.id ORDER BY rated_at DESC LIMIT 1) AS user_rating
                   FROM articles a JOIN sources s ON a.source_id = s.id
                   WHERE s.source_type = ? AND COALESCE(a.dismissed, 0) = 0
                   ORDER BY a.display_score DESC, a.fetched_at DESC LIMIT ?""",
                (source_type, limit),
            ).fetchall()
        else:
            # Fetch each source group sorted by its own metric, then interleave
            yt = con.execute(
                """SELECT a.*, s.name AS source_name, s.source_type,
                          (SELECT score FROM ratings WHERE article_id = a.id ORDER BY rated_at DESC LIMIT 1) AS user_rating
                   FROM articles a JOIN sources s ON a.source_id = s.id
                   WHERE s.source_type IN ('youtube', 'youtube_channel')
                     AND COALESCE(a.dismissed, 0) = 0
                   ORDER BY a.upvotes DESC, a.fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            rd = con.execute(
                """SELECT a.*, s.name AS source_name, s.source_type,
                          (SELECT score FROM ratings WHERE article_id = a.id ORDER BY rated_at DESC LIMIT 1) AS user_rating
                   FROM articles a JOIN sources s ON a.source_id = s.id
                   WHERE s.source_type = 'reddit'
                     AND COALESCE(a.dismissed, 0) = 0
                   ORDER BY a.upvotes DESC, a.fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            hn = con.execute(
                """SELECT a.*, s.name AS source_name, s.source_type,
                          (SELECT score FROM ratings WHERE article_id = a.id ORDER BY rated_at DESC LIMIT 1) AS user_rating
                   FROM articles a JOIN sources s ON a.source_id = s.id
                   WHERE s.source_type = 'hackernews'
                     AND COALESCE(a.dismissed, 0) = 0
                   ORDER BY a.display_score DESC, a.fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            rows = _interleave([yt, rd, hn], limit)
    return rows


def _interleave(groups: list, limit: int) -> list:
    """Round-robin interleave multiple ranked lists, skipping exhausted groups."""
    iters = [iter(g) for g in groups if g]
    result = []
    while iters and len(result) < limit:
        exhausted = []
        for it in iters:
            item = next(it, None)
            if item is None:
                exhausted.append(it)
            else:
                result.append(item)
                if len(result) >= limit:
                    break
        for it in exhausted:
            iters.remove(it)
    return result


def get_article_by_id(article_id: int) -> sqlite3.Row | None:
    with db_conn() as con:
        return con.execute(
            "SELECT a.*, s.name AS source_name, s.source_type FROM articles a JOIN sources s ON a.source_id = s.id WHERE a.id = ?",
            (article_id,),
        ).fetchone()


def get_existing_summary(external_id: str) -> str | None:
    """Return stored summary for an article if it exists and is non-empty, else None."""
    with db_conn() as con:
        row = con.execute(
            "SELECT summary FROM articles WHERE external_id = ? AND summary IS NOT NULL AND summary != ''",
            (external_id,),
        ).fetchone()
    return row["summary"] if row else None


def get_sources() -> list[sqlite3.Row]:
    with db_conn() as con:
        return con.execute(
            "SELECT * FROM sources WHERE COALESCE(blocked, 0) = 0 ORDER BY source_type, name"
        ).fetchall()


def get_keyword_weights() -> list[sqlite3.Row]:
    with db_conn() as con:
        return con.execute("SELECT * FROM keyword_weights ORDER BY weight DESC, keyword").fetchall()


def add_keyword_weight(keyword: str, weight: float) -> bool:
    """Add a keyword weight. Returns True if newly inserted."""
    kw = keyword.strip().lower()
    weight = max(0.1, min(5.0, weight))
    with db_conn() as con:
        cur = con.execute(
            "INSERT OR IGNORE INTO keyword_weights (keyword, weight) VALUES (?, ?)",
            (kw, weight),
        )
        return cur.rowcount > 0


def delete_keyword_weight(keyword_id: int) -> None:
    with db_conn() as con:
        con.execute("DELETE FROM keyword_weights WHERE id = ?", (keyword_id,))


def add_source(name: str, source_type: str, identifier: str, weight: float = 1.0) -> bool:
    """Add a generic source row. Returns True if newly inserted."""
    weight = max(0.1, min(3.0, weight))
    with db_conn() as con:
        cur = con.execute(
            "INSERT OR IGNORE INTO sources (name, source_type, identifier, weight) VALUES (?, ?, ?, ?)",
            (name.strip(), source_type.strip(), identifier.strip(), weight),
        )
        return cur.rowcount > 0


def delete_source(source_id: int) -> None:
    with db_conn() as con:
        con.execute("DELETE FROM sources WHERE id = ?", (source_id,))


# Pricing per million tokens (update if Anthropic changes rates)
_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
}
_DEFAULT_PRICING = {"input": 0.80, "output": 4.00}


def log_api_usage(model: str, input_tokens: int, output_tokens: int, purpose: str = "") -> float:
    """Record an API call and return cost in USD."""
    rates = _PRICING.get(model, _DEFAULT_PRICING)
    cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
    with db_conn() as con:
        con.execute(
            "INSERT INTO api_usage (model, input_tokens, output_tokens, cost_usd, purpose) VALUES (?, ?, ?, ?, ?)",
            (model, input_tokens, output_tokens, cost, purpose),
        )
    return cost


def get_api_usage_summary() -> dict:
    """Return aggregated usage stats: total cost, tokens, per-model breakdown, last 30 days."""
    with db_conn() as con:
        totals = con.execute(
            """SELECT model, purpose,
                      SUM(input_tokens) AS input_tokens,
                      SUM(output_tokens) AS output_tokens,
                      SUM(cost_usd) AS cost_usd,
                      COUNT(*) AS calls
               FROM api_usage
               WHERE called_at >= datetime('now', '-30 days')
               GROUP BY model, purpose
               ORDER BY cost_usd DESC"""
        ).fetchall()
        overall = con.execute(
            """SELECT SUM(cost_usd) AS total_cost,
                      SUM(input_tokens) AS total_input,
                      SUM(output_tokens) AS total_output,
                      COUNT(*) AS total_calls
               FROM api_usage
               WHERE called_at >= datetime('now', '-30 days')"""
        ).fetchone()
        daily = con.execute(
            """SELECT DATE(called_at) AS day, SUM(cost_usd) AS cost_usd, COUNT(*) AS calls
               FROM api_usage
               WHERE called_at >= datetime('now', '-7 days')
               GROUP BY day ORDER BY day DESC"""
        ).fetchall()
    return {
        "totals": [dict(r) for r in totals],
        "overall": dict(overall) if overall else {},
        "daily": [dict(r) for r in daily],
    }


def get_dismissed_articles(limit: int = 200) -> list[sqlite3.Row]:
    """Return dismissed articles from the last 7 days, newest first."""
    with db_conn() as con:
        return con.execute(
            """SELECT a.*, s.name AS source_name, s.source_type,
                      (SELECT score FROM ratings WHERE article_id = a.id ORDER BY rated_at DESC LIMIT 1) AS user_rating
               FROM articles a JOIN sources s ON a.source_id = s.id
               WHERE a.dismissed = 1
                 AND (a.dismissed_at IS NULL OR a.dismissed_at >= datetime('now', '-7 days'))
               ORDER BY COALESCE(a.dismissed_at, a.fetched_at) DESC LIMIT ?""",
            (limit,),
        ).fetchall()


def purge_old_dismissed() -> int:
    """Delete dismissed articles older than 7 days. Returns count deleted."""
    with db_conn() as con:
        cur = con.execute(
            """DELETE FROM articles
               WHERE dismissed = 1
                 AND dismissed_at IS NOT NULL
                 AND dismissed_at < datetime('now', '-7 days')"""
        )
        return cur.rowcount


def get_setting(key: str, default: str = "") -> str:
    with db_conn() as con:
        row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with db_conn() as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


def get_recent_reddit_titles(days: int = 3) -> list[str]:
    """Return titles of Reddit articles fetched in the last N days (for dedup)."""
    with db_conn() as con:
        rows = con.execute(
            """SELECT a.title FROM articles a
               JOIN sources s ON a.source_id = s.id
               WHERE s.source_type = 'reddit'
                 AND a.fetched_at >= datetime('now', ?)""",
            (f"-{days} days",),
        ).fetchall()
    return [r["title"] for r in rows]


def upsert_article(source_id: int, external_id: str, title: str, url: str,
                   summary: str, author: str, published_at, relevancy_score: float,
                   display_score: float, thumbnail_url: str, upvotes: int,
                   num_comments: int = 0) -> bool:
    """
    Insert article if new (returns True).
    If it already exists but has an empty summary, patch the summary (returns False).
    """
    with db_conn() as con:
        cur = con.execute(
            """INSERT OR IGNORE INTO articles
               (source_id, external_id, title, url, summary, author, published_at,
                relevancy_score, display_score, thumbnail_url, upvotes, num_comments)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_id, external_id, title, url, summary, author, published_at,
             relevancy_score, display_score, thumbnail_url, upvotes, num_comments),
        )
        if cur.rowcount > 0:
            return True
        # Patch summary on existing article if it was empty or a short placeholder
        if summary and len(summary) > 500:
            con.execute(
                """UPDATE articles SET summary = ?
                   WHERE source_id = ? AND external_id = ?
                     AND (summary IS NULL OR LENGTH(summary) < 500)""",
                (summary, source_id, external_id),
            )
        return False


def get_dismissed_titles(days: int = 30) -> list[str]:
    """Return titles of manually dismissed articles from the last N days."""
    with db_conn() as con:
        rows = con.execute(
            """SELECT title FROM articles
               WHERE dismissed = 1 AND COALESCE(auto_dismissed, 0) = 0
                 AND dismissed_at >= datetime('now', ?)
               ORDER BY dismissed_at DESC""",
            (f"-{days} days",),
        ).fetchall()
    return [r["title"] for r in rows]


def auto_dismiss_articles(article_ids: list[int]) -> int:
    """Mark articles as auto-dismissed. Returns count updated."""
    if not article_ids:
        return 0
    with db_conn() as con:
        placeholders = ",".join("?" * len(article_ids))
        cur = con.execute(
            f"""UPDATE articles
                SET dismissed = 1, auto_dismissed = 1, dismissed_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders}) AND COALESCE(dismissed, 0) = 0""",
            article_ids,
        )
        return cur.rowcount
