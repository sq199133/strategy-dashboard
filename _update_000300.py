# -*- coding: utf-8 -*-
"""更新000300指数文件到今日"""
import json, time
from pathlib import Path

HISTORY = Path(r"D:\QClaw_Trading\data\history")
hf = HISTORY / "000300.json"

try:
    import baostock as bs
    bs.login()
    rs = bs.query_history_k_data_plus(
        "sh.000300",
        "date,open,high,low,close,volume",
        start_date="2026-07-10", end_date="2026-07-13",
        frequency="d", adjustflag="3"
    )
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    bs.logout()
    print(f"Baostock returned {len(rows)} rows for 000300")
    if rows:
        for r in rows:
            print(f"  {r}")
except ImportError:
    print("baostock not installed")
except Exception as e:
    print(f"Error: {e}")
