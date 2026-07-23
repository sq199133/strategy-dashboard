"""主动防御层：随机延迟 + UA池 + Referer轮换 + 失败退避
"""
import random
import time
import requests
from collections import defaultdict
from pathlib import Path
import json


class AntiBlockDefense:
    """五层防御之 L2 主动防御：让请求行为看起来像真人浏览器"""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    REFERERS = [
        "https://finance.sina.com.cn/",
        "https://vip.stock.finance.sina.com.cn/",
        "https://stock.finance.sina.com.cn/",
        "https://www.eastmoney.com/",
        "https://quote.eastmoney.com/",
        "https://stockapp.finance.qq.com/",
    ]

    def __init__(self, min_delay: float = 0.3, max_delay: float = 1.2,
                 stats_path: str = None):
        """Args:
            min_delay: 基础最小延迟(秒)
            max_delay: 基础最大延迟(秒)
            stats_path: 失败统计持久化路径
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.session = requests.Session()
        self._last_request_at = 0.0
        self._fail_streak: dict = defaultdict(int)  # source -> consecutive fails
        self._last_sleep: float = 0.0
        self._stats_path = Path(stats_path) if stats_path else None
        if self._stats_path and self._stats_path.exists():
            try:
                self._fail_streak = defaultdict(int, json.loads(self._stats_path.read_text(encoding="utf-8")))
            except Exception:
                pass

    def get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": random.choice(self.REFERERS),
            "Connection": "keep-alive",
        }

    def throttle(self, source_name: str = "default", force_long: bool = False):
        """自适应节流：基础延迟 + 失败时退避
        Args:
            source_name: 源名（用于失败退避独立计数）
            force_long: 强制长延迟（>2秒），用于失败重试场景
        """
        now = time.time()
        streak = self._fail_streak.get(source_name, 0)

        if force_long:
            target = random.uniform(2.0, 5.0) * (1 + streak * 0.5)
        else:
            # 基础延迟 + 失败退避(每连败一次 ×1.5)
            base = random.uniform(self.min_delay, self.max_delay)
            target = base * (1 + streak * 0.5)

        elapsed = now - self._last_request_at
        if elapsed < target:
            sleep_time = target - elapsed
            time.sleep(sleep_time)
            self._last_sleep = sleep_time
        self._last_request_at = time.time()

    def report_success(self, source_name: str):
        self._fail_streak[source_name] = 0
        self._persist()

    def report_failure(self, source_name: str):
        self._fail_streak[source_name] = self._fail_streak.get(source_name, 0) + 1
        self._persist()

    def get_fail_streak(self, source_name: str) -> int:
        return self._fail_streak.get(source_name, 0)

    def reset_streak(self, source_name: str):
        self._fail_streak[source_name] = 0
        self._persist()

    def _persist(self):
        if self._stats_path:
            try:
                self._stats_path.parent.mkdir(parents=True, exist_ok=True)
                self._stats_path.write_text(
                    json.dumps(dict(self._fail_streak), ensure_ascii=False, indent=2),
                    encoding="utf-8")
            except Exception:
                pass  # 持久化失败不影响主流程

    def get(self, url: str, source_name: str = "default",
            params: dict = None, timeout: int = 15, max_retries: int = 2) -> requests.Response:
        """带防封策略的GET请求
        Returns: Response对象（失败时raise）
        """
        last_exc = None
        for attempt in range(max_retries + 1):
            self.throttle(source_name, force_long=(attempt > 0))
            try:
                resp = self.session.get(
                    url, params=params, headers=self.get_headers(),
                    timeout=timeout, allow_redirects=True)
                if resp.status_code == 200:
                    self.report_success(source_name)
                    return resp
                else:
                    self.report_failure(source_name)
                    last_exc = Exception(f"HTTP {resp.status_code}")
            except Exception as e:
                self.report_failure(source_name)
                last_exc = e
        raise last_exc
