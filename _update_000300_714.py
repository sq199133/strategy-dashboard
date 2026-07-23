# -*- coding: utf-8 -*-
import baostock as bs, json
from pathlib import Path

HISTORY = Path(r"D:\QClaw_Trading\data\history")
hf = HISTORY / "000300.json"

bs.login()
rs = bs.query_history_k_data_plus(
    "sh.000300", "date,open,high,low,close,volume",
    start_date="2026-07-14", end_date="2026-07-14",
    frequency="d", adjustflag="3"
)
rows = []
while rs.error_code == "0" and rs.next():
    rows.append(rs.get_row_data())
bs.logout()

if rows:
    today, o, h, l, c, v = rows[0]
    with open(hf, encoding="utf-8") as f:
        obj = json.load(f)
    recs = obj["records"]
    if recs[-1]["date"] != today:
        recs.append({
            "date": today, "open": round(float(o), 4),
            "high": round(float(h), 4), "low": round(float(l), 4),
            "close": round(float(c), 4), "vol": int(float(v)),
            "amount": 0, "chg": 0.0,
        })
        obj["records"] = recs
        obj["update"] = today
        with open(hf, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=None, separators=(",", ":"))
        print(f"+ 000300 {today} C={c}")
    else:
        print(f"000300 already {today}")
else:
    print("No data from baostock")
