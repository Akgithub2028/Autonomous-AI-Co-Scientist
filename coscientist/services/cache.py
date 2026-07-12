import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

class DiskCache:
    def __init__(self, cache_dir: str = "~/.coscientist/cache"):
        self.cache_dir = Path(os.path.expanduser(cache_dir))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_key(self, namespace: str, content: str) -> str:
        """Generate a SHA-256 hash for the given content."""
        content_bytes = content.encode('utf-8')
        hash_str = hashlib.sha256(content_bytes).hexdigest()
        return f"{namespace}_{hash_str}"

    def _get_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, namespace: str, content: str) -> Optional[Any]:
        """Retrieve an item from the cache."""
        key = self._get_key(namespace, content)
        path = self._get_path(key)
        
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.debug(f"Cache hit for {namespace}")
                    return data.get('value')
            except Exception as e:
                logger.warning(f"Failed to read cache {key}: {e}")
                
        return None

    def set(self, namespace: str, content: str, value: Any) -> None:
        """Store an item in the cache."""
        key = self._get_key(namespace, content)
        path = self._get_path(key)
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'value': value}, f)
                logger.debug(f"Cache set for {namespace}")
        except Exception as e:
            logger.warning(f"Failed to write cache {key}: {e}")

# Global cache instance
global_cache = DiskCache()
