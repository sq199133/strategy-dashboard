#!/usr/bin/env python3
"""Update all 312 ETF files to latest date."""
import json, time, random, requests
from datetime import datetime
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")

all_files = sorted([fp for fp in HISTORY.glob("*.json") if not fp.stem.startswith("_")])
print(f"文件: {len(all_files)}个\n")

def code_market(code):
    return "sh" if str(code).startswith(("6", "5")) else "sz"

upd = 0
err = 0
add = 0

for i, fp in enumerate(all_files):
    code = fp.stem
    mkt = code_market(code)
    
    try:
        r = requests.get(
            f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"CN_MarketData.getKLineData?symbol={mkt}{code}&scale=240&datalen=50",
            timeout=15)
        if r.status_code != 200: err+=1; continue
        nd = r.json()
        if not nd or not isinstance(nd, list): err+=1; continue
        
        new_recs = []
        for row in nd:
            day = row["day"].split()[0]
            new_recs.append({
                "date": day, "open": float(row["open"]), "close": float(row["close"]),
                "high": float(row["high"]), "low": float(row["low"]),
                "vol": int(float(row.get("volume", 0))), "amount": 0, "chg": 0.0
            })
        new_recs.sort(key=lambda r: r["date"])
        
        old = json.loads(fp.read_text(encoding="utf-8"))
        old_recs = old.get("records", [])
        adj = old.get("adjustments", [])
        
        seen = set()
        merged = []
        for r in new_recs:
            seen.add(r["date"]); merged.append(r)
        for r in old_recs:
            if r["date"] not in seen: merged.append(r)
        merged.sort(key=lambda r: r["date"])
        
        a = len(merged) - len(old_recs)
        if a > 0:
            fp.write_text(
                json.dumps({"code": code, "name": old.get("name", ""),
                           "records": merged, "adjustments": adj},
                           ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8")
            upd+=1; add+=a
            if i%30==0 or i==len(all_files)-1:
                print(f"  [{i+1}/{len(all_files)}] {code} +{a} {merged[0]['date']}~{merged[-1]['date']}")
        
        time.sleep(random.uniform(0.12, 0.3))
    
    except Exception as e:
        err+=1
        if err<=3: print(f"  [{i+1}/{len(all_files)}] {code} ✗ {str(e)[:50]}")

print(f"\n✅ 更新: {upd}/{len(all_files)} +{add}条, 错误{err}")

# Sync weekly
print(f"\n同步周线...")
wk = 0
for fp in all_files:
    code = fp.stem
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", [])
    if not recs: continue
    adj = raw.get("adjustments", [])
    weekly = []
    wd = []
    for j, r in enumerate(recs):
        d = datetime.strptime(r["date"], "%Y-%m-%d").date()
        wd.append(r)
        if d.weekday() == 4 or j == len(recs) - 1:
            cp = float(r["close"])
            weekly.append({
                "w": f'{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}',
                "date": r["date"], "close": round(cp, 4),
                "open": round(float(wd[0].get("open", cp)), 4),
                "high": round(max(float(x.get("high", cp)) for x in wd), 4),
                "low": round(min(float(x.get("low", cp)) for x in wd), 4),
                "vol": sum(float(x.get("vol", 0)) for x in wd),
            })
            wd = []
    (LONG_V2 / f"{code}.json").write_text(
        json.dumps({"code": code, "name": raw.get("name",""), "records": weekly,
                    "update": recs[-1]["date"], "adjustments": adj} if adj
                   else {"code": code, "name": raw.get("name",""), "records": weekly,
                         "update": recs[-1]["date"]},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    wk += 1
print(f"周线: {wk}个")

# Summary
from collections import Counter
latest = {}
for fp in all_files:
    d = json.loads(fp.read_text(encoding="utf-8"))
    r = d.get("records", [])
    if r: latest[fp.stem] = r[-1]["date"]
ct = Counter(latest.values())
print(f"\n=== 最新日期分布 ===")
for d, c in sorted(ct.items(), reverse=True):
    m = " ✅" if d == max(ct.keys()) else ""
    print(f"  {d}: {c}只{m}")
print(f"\n总记录: {sum(len(json.loads(fp.read_text(encoding='utf-8')).get('records',[])) for fp in all_files)}")
