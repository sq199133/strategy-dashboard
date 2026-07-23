# -*- coding: utf-8 -*-
"""
集思录 (jisilu.cn) 数据接口
通过 cookie 授权获取可转债/ETF/指数估值等数据

Usage:
    from jisilu import JisiluAPI
    api = JisiluAPI(cookie="kbzw__Session=...")
    df = api.convertible_bonds()  # 可转债全表
    df = api.convertible_bond("123456")  # 某只转债详情
"""

import json, time, os
import urllib.request, urllib.parse
from typing import Optional

try:
    import pandas as pd
    HAS_PD = True
except:
    HAS_PD = False


class JisiluAPI:
    """集思录 API 封装"""

    BASE = "https://www.jisilu.cn"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.jisilu.cn/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    def __init__(self, cookie: str = ""):
        self.cookie = cookie
        self._last_request = 0

    def set_cookie(self, cookie_str: str):
        self.cookie = cookie_str

    def _req(self, url: str, retries=2) -> dict:
        """发送 GET 请求"""
        elapsed = time.time() - self._last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        headers = self.HEADERS.copy()
        if self.cookie:
            headers["Cookie"] = self.cookie

        req = urllib.request.Request(url, headers=headers)
        for attempt in range(retries):
            try:
                resp = urllib.request.urlopen(req, timeout=30)
                self._last_request = time.time()
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

    def convertible_bonds(self) -> "pd.DataFrame":
        """获取全市场可转债列表 (GET)"""
        url = f"{self.BASE}/webapi/cb/list/"
        params = urllib.parse.urlencode({"qtype": "ALL", "rp": 50, "page": 1})
        resp = self._req(f"{url}?{params}")
        data = resp.get("data", [])
        if not data:
            if HAS_PD:
                return pd.DataFrame()
            return []

        if HAS_PD:
            return pd.DataFrame(data)
        return data

    def convertible_bond(self, bond_id: str) -> dict:
        """获取单只可转债详情"""
        url = f"{self.BASE}/webapi/cb/detail/"
        params = urllib.parse.urlencode({"bond_id": bond_id})
        return self._req(f"{url}?{params}")

    def etf_list(self) -> list:
        """获取集思录 ETF 列表（含实时溢价）"""
        resp = self._req(f"{self.BASE}/webapi/etf/list/")
        return resp.get("data", [])

    def index_valuation(self) -> list:
        """获取指数估值"""
        resp = self._req(f"{self.BASE}/webapi/index/valuation/")
        return resp.get("data", [])

    def __repr__(self):
        return f"JisiluAPI(cookie_set={bool(self.cookie)})"


# ---- CLI ----
if __name__ == "__main__":
    import sys
    api = JisiluAPI(cookie=os.environ.get("JISILU_COOKIE", ""))

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "cb":
            df = api.convertible_bonds()
            print(f"可转债: {len(df)} 只")
            if HAS_PD:
                cols = [c for c in ["bond_id","bond_nm","price","convert_price","premium_rt","pb","ytm_rt"] if c in df.columns]
                print(df[cols].head(5).to_string())
            else:
                print("前3只:", df[:3] if df else "空")
        elif cmd == "etf":
            data = api.etf_list()
            print(f"ETF: {len(data)} 只, 前3:", data[:3] if data else "空")
        elif cmd == "index":
            data = api.index_valuation()
            print(f"指数: {len(data)} 只")
            if data: print(data[:3])
    else:
        print("Usage: python jisilu.py cb|etf|index")
        print("Set env JISILU_COOKIE or use set_cookie()")
