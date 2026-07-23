"""本地缓存层 L4：减少80%外网请求
策略：
- kline_daily: backbone永久 + 增量TTL 1天
- real_time: TTL 0 (不缓存)
- fundamentals: TTL 1天
"""
import json
import time
from pathlib import Path
from typing import Any, Optional


class CacheManager:
    """本地JSON缓存：减少外网请求的最后一公里"""

    DEFAULT_TTL = {
        "kline_daily": 86400,       # 1天
        "kline_weekly": 86400 * 7,  # 1周
        "real_time_quote": 0,       # 不缓存
        "fundamentals": 86400,      # 1天
        "fund_flow": 3600,          # 1小时
        "dividend": 86400 * 30,     # 1月
        "pe_pb": 86400,             # 1天
    }

    def __init__(self, cache_dir: str = "D:/QClaw_Trading/data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.cache_dir / "_index.json"
        self._index = self._load_index()

    def _load_index(self) -> dict:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_index(self):
        try:
            self._index_path.write_text(
                json.dumps(self._index, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:
            pass

    def _cache_path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe}.json"

    def get(self, key: str, ttl: int = 0) -> Optional[Any]:
        """获取缓存
        Args:
            key: 缓存键
            ttl: 过期时间(秒)，0=不过期
        Returns:
            缓存值 or None(过期/不存在)
        """
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            meta = self._index.get(key, {})
            if ttl > 0 and meta.get("ts", 0) + ttl < time.time():
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = None):
        """设置缓存"""
        path = self._cache_path(key)
        path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
        self._index[key] = {
            "ts": time.time(),
            "ttl": ttl,
            "size": path.stat().st_size,
        }
        self._save_index()

    def delete(self, key: str):
        path = self._cache_path(key)
        if path.exists():
            path.unlink()
        self._index.pop(key, None)
        self._save_index()

    def clear_expired(self):
        """清理所有过期缓存"""
        now = time.time()
        to_delete = []
        for key, meta in self._index.items():
            ttl = meta.get("ttl", 0)
            if ttl and meta.get("ts", 0) + ttl < now:
                to_delete.append(key)
        for k in to_delete:
            self.delete(k)
        return len(to_delete)

    def stats(self) -> dict:
        total_size = sum(m.get("size", 0) for m in self._index.values())
        return {
            "entries": len(self._index),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "expired": sum(1 for m in self._index.values()
                          if m.get("ttl") and m["ts"] + m["ttl"] < time.time()),
        }
