"""Force-refresh ETFs that are still stuck at 2026-06-25.
Use Sina directly (not DataFetcher cache) to get latest data.
"""
import json, time, random, requests
from pathlib import Path

HIST = Path("D:/QClaw_Trading/data/history")
STUCK = ["159901", "510050", "159915", "512690", "159928"]  # add more as needed

def code_market(code):
    c = str(code).zfill(6)
    if c.startswith(("60", "68", "9", "5", "11")):
        return "sh"
    return "sz"

def fetch_sina_fresh(code, datalen=20):
    """Fetch fresh data from Sina VIP, bypass cache."""
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
    except Exception as e:
        print(f"    Error: {e}")
        return None

for code in STUCK:
    fp = HIST / f"{code}.json"
    if not fp.exists():
        print(f"{code}: file not found, skip")
        continue

    # Load local
    for enc in ["utf-8", "gbk", "gb18030"]:
        try:
            local = json.loads(fp.read_bytes().decode(enc))
            break
        except:
            local = None
    if not local:
        print(f"{code}: bad file")
        continue

    recs = local.get("records", local) if isinstance(local, dict) else local
    local_dates = set(r["date"] for r in recs if isinstance(r, dict) and "date" in r)
    last_local = max(local_dates) if local_dates else "N/A"

    # Fetch fresh
    fresh = fetch_sina_fresh(code, 20)
    if not fresh:
        print(f"{code}: API error, last={last_local}")
        time.sleep(0.5)
        continue

    fresh_dates = set(r["day"].split()[0] for r in fresh if "day" in r)
    new_dates = fresh_dates - local_dates

    if not new_dates:
        last_api = max(fresh_dates)
        print(f"{code}: already current ({last_api}), local={last_local}")
    else:
        # Append new records
        rec_map = {r["date"]: r for r in recs if isinstance(r, dict) and "date" in r}
        for row in fresh:
            d = row["day"].split()[0]
            if d in new_dates:
                rec_map[d] = {
                    "date": d,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"]),
                }
        new_recs = sorted(rec_map.values(), key=lambda x: x["date"])

        if isinstance(local, dict):
            local["records"] = new_recs
            fp.write_text(json.dumps(local, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        else:
            fp.write_text(json.dumps(new_recs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        print(f"{code}: +{len(new_dates)} new dates {sorted(new_dates)} (was {last_local})")

    time.sleep(random.uniform(0.4, 1.0))

print("\nDone")
