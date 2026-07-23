# -*- coding: utf-8 -*-
import json, urllib.request, time
from pathlib import Path

HISTORY = Path(r"D:\QClaw_Trading\data\history")
UA = {"User-Agent": "Mozilla/5.0", "Referer": "http://finance.sina.com.cn"}

code = "159773"
url = (f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
       f"CN_MarketData.getKLineData?symbol=sz{code}&scale=240&datalen=5")
req = urllib.request.Request(url, headers=UA)
resp = urllib.request.urlopen(req, timeout=25)
data = json.loads(resp.read().decode("utf-8", errors="replace"))
if not data:
    print(f"EMPTY {code}"); exit()
today_rec = data[-1]
today = today_rec["day"].split()[0]
hf = HISTORY / f"{code}.json"
with open(hf, encoding="utf-8") as f:
    obj = json.load(f)
records = obj.get("records", [])
if records[-1]["date"] == today:
    print(f"SKIP {code} already {today}")
else:
    vol_key = "vol"
    with open(hf, encoding="utf-8") as f:
        txt = f.read()
    if '"volume":' in txt:
        vol_key = "volume"
    new_rec = {
        "date": today, "open": round(float(today_rec["open"]), 4),
        "high": round(float(today_rec["high"]), 4),
        "low": round(float(today_rec["low"]), 4),
        "close": round(float(today_rec["close"]), 4),
        vol_key: int(float(today_rec.get("volume", 0))),
        "amount": 0, "chg": 0.0,
    }
    records.append(new_rec)
    obj["records"] = records
    obj["update"] = today
    with open(hf, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    print(f"+ {code} {today} C={new_rec['close']} V={new_rec[vol_key]:,}")
