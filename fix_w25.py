"""Fix 6/19 (Thu) missing data for all 195 ETFs.
6/20 and 6/21 are weekend - skip those.
"""
import json, time, random, requests
from pathlib import Path

HIST = Path("D:/QClaw_Trading/data/history")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")

pool = json.loads(POOL.read_text(encoding="utf-8"))["data"]

def code_market(code):
    c = str(code).zfill(6)
    if c.startswith(("60", "68", "9", "5", "11")):
        return "sh"
    return "sz"

def fetch_sina(code, datalen=10):
    mkt = code_market(code)
    url = (f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={mkt}{code}&scale=240&datalen={datalen}")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data or not isinstance(data, list):
            return None
        return data
    except:
        return None

target = "2026-06-19"
updated = 0
errors = 0

for i, item in enumerate(pool):
    code = item["code"]
    fp = HIST / f"{code}.json"
    if not fp.exists():
        errors += 1
        continue

    for enc in ["utf-8", "gbk", "gb18030"]:
        try:
            local = json.loads(fp.read_bytes().decode(enc))
            break
        except:
            local = None
    if not local:
        errors += 1
        continue

    recs = local.get("records", local) if isinstance(local, dict) else local
    local_dates = set(r["date"] for r in recs if isinstance(r, dict) and "date" in r)

    if target in local_dates:
        if (i+1) % 50 == 0:
            print(f"  [{i+1}/{len(pool)}] {code}: {target} already present")
        continue

    fresh = fetch_sina(code, 15)
    if not fresh:
        print(f"  [{i+1}/{len(pool)}] {code}: API error")
        errors += 1
        continue

    fresh_map = {r["day"].split()[0]: {
        "date": r["day"].split()[0],
        "open": float(r["open"]),
        "high": float(r["high"]),
        "low": float(r["low"]),
        "close": float(r["close"]),
        "volume": int(r["volume"]),
    } for r in fresh if "day" in r}

    if target not in fresh_map:
        print(f"  [{i+1}/{len(pool)}] {code}: API also missing {target}")
        errors += 1
        continue

    rec_map = {r["date"]: r for r in recs if isinstance(r, dict) and "date" in r}
    rec_map[target] = fresh_map[target]
    new_recs = sorted(rec_map.values(), key=lambda x: x["date"])

    if isinstance(local, dict):
        local["records"] = new_recs
        fp.write_text(json.dumps(local, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    else:
        fp.write_text(json.dumps(new_recs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"  [{i+1}/{len(pool)}] {code}: +{target}")
    updated += 1
    time.sleep(random.uniform(0.3, 0.8))

print(f"\nDone: +{updated} updated, {errors} errors")
