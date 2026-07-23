# -*- coding: utf-8 -*-
import json
from pathlib import Path

HISTORY = Path(r"D:\QClaw_Trading\data\history")
hf = HISTORY / "000300.json"
today = "2026-07-13"
new_row = ["2026-07-13", 4745.4383, 4775.2355, 4670.2496, 4695.3830, 27863485300]

with open(hf, encoding="utf-8") as f:
    obj = json.load(f)
records = obj.get("records", [])
last_date = records[-1]["date"] if records else "1900-01-01"

if last_date == today:
    print(f"000300 already has {today}")
else:
    # 000300 uses "vol" not "volume"
    new_rec = {
        "date": today,
        "open": round(new_row[1], 4),
        "high": round(new_row[2], 4),
        "low": round(new_row[3], 4),
        "close": round(new_row[4], 4),
        "vol": int(new_row[5]),
        "amount": 0,
        "chg": 0.0,
    }
    records.append(new_rec)
    obj["records"] = records
    obj["update"] = today
    with open(hf, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    print(f"+ 000300 {today} C={new_rec['close']} V={new_rec['vol']:,}")
