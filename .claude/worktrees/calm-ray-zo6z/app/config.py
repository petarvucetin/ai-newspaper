import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

load_dotenv()

_BASE = Path(__file__).parent.parent
_config_path = _BASE / "config.yaml"

with open(_config_path) as f:
    _cfg = yaml.safe_load(f)


def get(key: str, default=None):
    """Dot-notation access into config.yaml, e.g. get('server.port')."""
    parts = key.split(".")
    node = _cfg
    for p in parts:
        if not isinstance(node, dict):
            return default
        node = node.get(p, default)
        if node is default:
            return default
    return node


def raw() -> dict:
    return _cfg


# No secrets required — Reddit uses the public JSON API, YouTube uses yt-dlp.
