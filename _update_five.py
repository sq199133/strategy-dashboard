# -*- coding: utf-8 -*-
"""更新5只ETF到最新 + 补周线"""
import json, urllib.request, time
from pathlib import Path

HISTORY = Path(r"D:\QClaw_Trading\data\history")
WEEKLY = Path(r"D:\QClaw_Trading\data\history_long_v2")
UA = {"User-Agent": "Mozilla/5.0", "Referer": "http://finance.sina.com.cn"}

codes = {"510050": "sh", "159915": "sz", "513500": "sh", "513100": "sh", "515080": "sh"}

# Probe today
pu = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz159915&scale=240&datalen=3"
today = json.loads(urllib.request.urlopen(urllib.request.Request(pu, headers=UA), timeout=15).read().decode("utf-8"))[-1]["day"].split()[0]
print(f"Today: {today}")

for code, mkt in codes.items():
    try:
        ku = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={mkt}{code}&scale=240&datalen=100"
        klines = json.loads(urllib.request.urlopen(urllib.request.Request(ku, headers=UA), timeout=20).read().decode("utf-8"))
        if not klines: continue
        hf = HISTORY / f"{code}.json"
        if not hf.exists():
            print(f"  NOFILE {code}"); continue
        vol_key = "vol" if b'"vol":' in open(hf,"rb").read() else "volume"
        with open(hf, encoding="utf-8") as f: obj = json.load(f)
        recs = obj.get("records", [])
        last = recs[-1]["date"] if recs else ""
        added = 0
        for r in klines:
            rd = r["day"].split()[0]
            if rd <= last: continue
            recs.append({"date":rd,"open":round(float(r["open"]),4),
                "high":round(float(r["high"]),4),"low":round(float(r["low"]),4),
                "close":round(float(r["close"]),4),vol_key:int(float(r.get("volume",0))),
                "amount":0,"chg":0.0})
            added += 1
        if added:
            obj["records"] = recs; obj["update"] = recs[-1]["date"]
            with open(hf,"w",encoding="utf-8") as f:
                json.dump(obj,f,ensure_ascii=False,indent=None,separators=(",",":"))
        print(f"  {code}: 从 {last} +{added} 条 → {recs[-1]['date']}")
        time.sleep(0.15)
    except Exception as e:
        print(f"  ERR {code}: {e}")

print("\n日线更新完成")
