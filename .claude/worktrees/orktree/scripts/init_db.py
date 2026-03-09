#!/usr/bin/env python3
# Run with: python3 scripts/init_db.py
"""One-time (or idempotent) database initialization."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, seed_keywords, seed_sources
from app import config

init_db()
seed_keywords(config.get("keyword_weights", {}))
seed_sources(config.get("sources", {}))
print("Done.")
