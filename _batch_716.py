# -*- coding: utf-8 -*-
"""Sina 批量快照更新日线到 2026-07-16"""
import json, re, urllib.request, time
from pathlib import Path

HISTORY = Path(r"D:\QClaw_Trading\data\history")
POOL_FILE = Path(r"D:\QClaw_Trading\data\etf_pool_V1_full.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "http://finance.sina.com.cn"}

def load_pool_codes():
    with open(POOL_FILE, encoding="utf-8") as f:
        obj = json.load(f)
    codes = [item["code"] for item in obj["data"]]
    for fc in ["512890", "515910", "512750", "159399"]:
        if fc not in codes:
            codes.append(fc)
    return codes

codes = load_pool_codes()
url = "http://hq.sinajs.cn/list=" + ",".join(
    f"sh{c}" if (c[0]=="5" or re.match(r"^1[15]\d{4}$",c)) else f"sz{c}"
    for c in codes)
req = urllib.request.Request(url, headers=UA)
resp = urllib.request.urlopen(req, timeout=30)
raw_text = resp.read().decode("gb18030", errors="replace")

spot_data = {}
for m in re.finditer(r'hq_str_(?:sh|sz)(\w+)="([^"]+)"', raw_text):
    code, fields_str = m.group(1), m.group(2)
    fields = [f.strip() for f in fields_str.split(",")]
    if len(fields) < 9: continue
    date_str = None
    for fi in range(-6, -1):
        if re.match(r"\d{4}-\d{2}-\d{2}", fields[fi]):
            date_str = fields[fi]; break
    if not date_str: continue
    try:
        spot_data[code] = {
            "date": date_str, "open": float(fields[1]), "prev": float(fields[2]),
            "low": float(fields[3]), "high": float(fields[4]), "close": float(fields[5]),
            "vol": int(float(fields[12] if len(fields)>12 else fields[7])),
        }
    except: continue

print(f"[Phase1] 快照: {len(spot_data)}/{len(codes)}")

detect_vol_key = lambda hf: "vol" if b'"vol":' in open(hf,"rb").read() else "volume"

updated1 = 0
for code in codes:
    if code not in spot_data: continue
    hf = HISTORY / f"{code}.json"
    if not hf.exists(): continue
    try:
        s = spot_data[code]
        vol_key = detect_vol_key(hf)
        with open(hf, encoding="utf-8") as f: obj = json.load(f)
        recs = obj.get("records", [])
        if recs and recs[-1]["date"] == s["date"]: continue
        recs.append({"date": s["date"], "open": round(s["open"],4),
            "high": round(s["high"],4), "low": round(s["low"],4),
            "close": round(s["close"],4), vol_key: s["vol"], "amount":0, "chg":0.0})
        obj["records"] = recs; obj["update"] = s["date"]
        with open(hf, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=None, separators=(",",":"))
        pct = (s["close"]/s["prev"]-1)*100 if s["prev"] else 0
        print(f"  + {code} {s['date']} C={s['close']:.4f} ({pct:+.2f}%)")
        updated1 += 1
    except Exception as e:
        print(f"  ERR {code}: {e}")

print(f"[Phase1] updated={updated1}")

# Phase2: 159xxx
missing159 = [c for c in codes if c.startswith("159") and c not in spot_data]
if missing159:
    print(f"[Phase2] 补159xxx ({len(missing159)}只)...")
    # probe today
    pu = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz159915&scale=240&datalen=3"
    today = json.loads(urllib.request.urlopen(urllib.request.Request(pu, headers=UA), timeout=15).read().decode("utf-8"))[-1]["day"].split()[0]
    updated2 = 0
    for code in missing159:
        try:
            ku = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz{code}&scale=240&datalen=3"
            klines = json.loads(urllib.request.urlopen(urllib.request.Request(ku, headers=UA), timeout=20).read().decode("utf-8"))
            daily = next((r for r in klines if r["day"].startswith(today)), None)
            if not daily: continue
            hf = HISTORY / f"{code}.json"
            if not hf.exists(): continue
            vol_key = detect_vol_key(hf)
            with open(hf, encoding="utf-8") as f: obj = json.load(f)
            recs = obj.get("records", [])
            if recs and recs[-1]["date"] == today: continue
            new_rec = {"date": today, "open": round(float(daily["open"]),4),
                "high": round(float(daily["high"]),4), "low": round(float(daily["low"]),4),
                "close": round(float(daily["close"]),4), vol_key: int(float(daily.get("volume",0))),
                "amount":0, "chg":0.0}
            recs.append(new_rec); obj["records"] = recs; obj["update"] = today
            with open(hf, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=None, separators=(",",":"))
            pct = (new_rec["close"]/new_rec["open"]-1)*100 if new_rec["open"] else 0
            print(f"  + {code} {today} C={new_rec['close']:.4f} ({pct:+.2f}%)")
            updated2 += 1
        except Exception as e:
            print(f"  ERR {code}: {e}")
        time.sleep(0.12)
    print(f"[Phase2] updated={updated2}")

print("=== 日线更新完成 ===")
