"""L5 健康监控：自动降级 + 熔断 + 自愈
"""
import time
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict


class HealthMonitor:
    """熔断器：连续失败N次 → 自动跳过该源 → 每N分钟重试自愈"""

    def __init__(self, state_path: str = None,
                 fail_threshold: int = 5,
                 cooldown_minutes: int = 30):
        self.fail_threshold = fail_threshold
        self.cooldown_seconds = cooldown_minutes * 60
        self.state_path = Path(state_path) if state_path else None
        self._state: Dict[str, dict] = self._load()

    def _load(self) -> dict:
        if self.state_path and self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        if self.state_path:
            try:
                self.state_path.parent.mkdir(parents=True, exist_ok=True)
                self.state_path.write_text(
                    json.dumps(self._state, ensure_ascii=False, indent=2),
                    encoding="utf-8")
            except Exception:
                pass

    def is_available(self, source_name: str) -> bool:
        """检查源是否可用（未熔断）"""
        s = self._state.get(source_name, {})
        if s.get("circuit_broken_at"):
            if time.time() - s["circuit_broken_at"] > self.cooldown_seconds:
                # 冷却期到，恢复
                s.pop("circuit_broken_at", None)
                s["status"] = "recovered"
                self._save()
                return True
            return False
        return True

    def record_success(self, source_name: str):
        s = self._state.setdefault(source_name, {"fails": 0, "total": 0})
        s["fails"] = 0
        s["total"] = s.get("total", 0) + 1
        s["last_success"] = time.time()
        s.pop("circuit_broken_at", None)
        self._save()

    def record_failure(self, source_name: str):
        s = self._state.setdefault(source_name, {"fails": 0, "total": 0})
        s["fails"] = s.get("fails", 0) + 1
        s["total"] = s.get("total", 0) + 1
        s["last_failure"] = time.time()
        if s["fails"] >= self.fail_threshold and not s.get("circuit_broken_at"):
            s["circuit_broken_at"] = time.time()
        self._save()

    def get_status(self, source_name: str) -> dict:
        s = self._state.get(source_name, {})
        return {
            "fails": s.get("fails", 0),
            "total": s.get("total", 0),
            "success_rate": round((s.get("total", 0) - s.get("fails", 0)) / max(s.get("total", 1), 1) * 100, 1),
            "circuit_broken": bool(s.get("circuit_broken_at")),
            "last_success": s.get("last_success"),
            "last_failure": s.get("last_failure"),
        }

    def all_status(self) -> dict:
        return {name: self.get_status(name) for name in self._state}
