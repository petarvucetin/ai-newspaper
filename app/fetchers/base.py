from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawArticle:
    source_name: str        # Matches sources.name
    external_id: str        # Unique ID within that source
    title: str
    url: str
    summary: str = ""
    author: str = ""
    published_at: datetime = field(default_factory=datetime.utcnow)
    thumbnail_url: str = ""
    upvotes: int = 0
