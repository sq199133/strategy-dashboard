"""
Tencent Daily ETF Data Downloader v2
分段API调用，每只ETF分4段获取全量前复权日线数据
"""
import requests
import json
import os
import time

# ========== CONFIG ==========
OUTPUT_DIR = r"D:\QClaw_Trading\data\daily_tx"
API_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
RATE_LIMIT = 3  # seconds per request
MAX_RETRIES = 3
SEGMENTS = [
    ("2010-01-01", "2016-12-31"),
    ("2017-01-01", "2020-12-31"),
    ("2021-01-01", "2024-12-31"),
    ("2025-01-01", "2027-12-31"),
]

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========== GET ETF LIST FROM HISTORY ==========
history_dir = r"D:\QClaw_Trading\data\history_long"
existing_files = os.listdir(history_dir)
existing_codes = sorted([f.replace(".json", "") for f in existing_files if f.endswith(".json")])
print("ETF count in history_long: %d" % len(existing_codes))

# ========== DOWNLOAD SINGLE ETF ==========
def download_etf_daily(code):
    all_rows = {}
    for start, end in SEGMENTS:
        param_str = "%s,day,%s,%s,1000,qfq" % (code, start, end)
        params = {"_var": "kline_dayqfq", "param": param_str, "r": "0.751892490072597"}
        for retry in range(MAX_RETRIES):
            try:
                r = requests.get(API_URL, params=params, timeout=15)
                time.sleep(RATE_LIMIT)
                text = r.text
                if "={" not in text:
                    break
                json_str = text[text.find("=") + 1:]
                data = json.loads(json_str)
                dd = data.get("data", {})
                if isinstance(dd, dict):
                    sd = dd.get(code, {})
                    if isinstance(sd, dict):
                        klines = sd.get("qfqday", [])
                        for row in klines:
                            if row[0] not in all_rows:
                                all_rows[row[0]] = row
                break
            except Exception:
                if retry < MAX_RETRIES - 1:
                    time.sleep(2)
    return [all_rows[k] for k in sorted(all_rows.keys())]


def save_etf(code, rows):
    out_file = os.path.join(OUTPUT_DIR, "%s.json" % code)
    records = []
    for row in rows:
        try:
            records.append({
                "date": row[0],
                "open": float(row[1]),
                "close": float(row[2]),
                "high": float(row[3]),
                "low": float(row[4]),
                "volume": float(row[5]) if row[5] else 0.0,
            })
        except (IndexError, ValueError):
            continue
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "code": code,
            "total": len(records),
            "start": records[0]["date"] if records else "",
            "end": records[-1]["date"] if records else "",
            "data": records
        }, f, ensure_ascii=False, indent=False)
    return len(records)


# ========== MAIN LOOP ==========
total = len(existing_codes)
success = 0
fail_list = []
skipped = 0

for i, code in enumerate(existing_codes):
    out_file = os.path.join(OUTPUT_DIR, "%s.json" % code)
    
    # Skip if already exists with >= 1000 rows
    if os.path.exists(out_file):
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("total", 0) >= 1000:
                skipped += 1
                print("[%d/%d] [SKIP] %s: exists (%d rows)" % (i+1, total, code, existing.get("total")))
                continue
        except:
            pass
    
    print("[%d/%d] Downloading %s ... " % (i+1, total, code), end="", flush=True)
    rows = download_etf_daily(code)
    
    if len(rows) >= 500:
        count = save_etf(code, rows)
        success += 1
        print("OK: %d rows (%s to %s)" % (count, rows[0][0], rows[-1][0]))
    else:
        fail_list.append(code)
        print("FAIL: only %d rows (need >= 500)" % len(rows))

print()
print("=" * 50)
print("Done! Success: %d, Failed: %d, Skipped: %d" % (success, len(fail_list), skipped))
if fail_list:
    print("Failed: %s" % fail_list[:20])
