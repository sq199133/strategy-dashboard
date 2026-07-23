#!/usr/bin/env python3
"""
批量刷新所有ETF数据 + 同步周线
从Sina API重下载所有195只标的，与本地数据合并去重，再生成周线
"""
import json, sys, time, random, requests
from datetime import datetime, date
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
API_DELAY = (0.3, 0.8)

# === Load ===
pool = json.loads(POOL.read_text(encoding="utf-8"))["data"]
pool_codes = {e["code"]: e.get("name", "") for e in pool}

def code_market(code):
    c = str(code).strip()
    return "sh" if c.startswith(("6", "5")) else "sz"

def load_json_safe(fp):
    if not fp.exists():
        return None
    raw = fp.read_bytes()
    if len(raw) == 0:
        return None
    for enc in ["utf-8", "gbk"]:
        try: return json.loads(raw.decode(enc))
        except: continue
    return json.loads(raw.decode("gbk", errors="replace"))

def write_json_safe(fp, data):
    fp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

def get_records(d):
    return d.get("records", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])

def download_sina(code):
    market = code_market(code)
    url = (f"https://quotes.sina.cn/cn/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&datalen=1500")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or len(r.text) < 10:
            return None
        js = r.json()
        if not js:
            return None
        records = []
        for row in js:
            day = row["day"].split()[0]
            records.append({
                "date": day,
                "open": float(row["open"]),
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "vol": int(float(row.get("volume", 0))),
                "amount": int(float(row.get("amount", 0))),
                "chg": 0.0
            })
        records.sort(key=lambda r: r["date"])
        return records
    except Exception as e:
        return None

def merge_records(existing, new_records):
    """Merge new records into existing, dedup by date."""
    by_date = {}
    for r in existing:
        by_date[r["date"]] = r
    for r in new_records:
        if r["date"] not in by_date:
            by_date[r["date"]] = r
    result = sorted(by_date.values(), key=lambda x: x["date"])
    return result

def daily_to_weekly(daily_records):
    if not daily_records:
        return []
    weekly = []
    week_data = []
    for i, r in enumerate(daily_records):
        dt = datetime.strptime(r["date"], "%Y-%m-%d").date()
        iso_yr, iso_wk, iso_dow = dt.isocalendar()
        week_data.append(r)
        if dt.weekday() == 4 or i == len(daily_records) - 1:
            close_p = float(r["close"])
            open_p = float(week_data[0].get("open", close_p))
            high_p = float(max(x.get("high", close_p) for x in week_data))
            low_p = float(min(x.get("low", close_p) for x in week_data))
            vol = sum(float(x.get("vol", 0)) for x in week_data)
            rec = {"w": f"{iso_yr}-W{iso_wk:02d}", "date": r["date"], "close": round(close_p, 4)}
            if "open" in week_data[0]:
                rec["open"] = round(open_p, 4)
            if "high" in week_data[0]:
                rec["high"] = round(high_p, 4)
            if "low" in week_data[0]:
                rec["low"] = round(low_p, 4)
            if "vol" in week_data[0] or any("vol" in x for x in week_data):
                rec["vol"] = round(vol, 0)
            weekly.append(rec)
            week_data = []
    return weekly

# === Main ===
total = len(pool_codes)
print(f"📡 开始批量更新 {total} 只ETF...")
print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print()

updated_count = 0
updated_codes = []
skip_count = 0
error_count = 0
new_dates = set()

for i, (code, name) in enumerate(pool_codes.items()):
    fp = HISTORY / f"{code}.json"
    existing = []
    if fp.exists():
        raw = load_json_safe(fp)
        existing = get_records(raw)
    
    time.sleep(random.uniform(*API_DELAY))
    new_records = download_sina(code)
    
    if new_records is None:
        print(f"  ✗ {code} {name}: 下载失败")
        error_count += 1
        continue
    
    new_last = new_records[-1]["date"]
    old_last = existing[-1]["date"] if existing else "N/A"
    
    if existing:
        merged = merge_records(existing, new_records)
        added = len(merged) - len(existing)
    else:
        merged = new_records
        added = len(merged)
    
    # Find truly new dates (beyond what we already had)
    old_dates = {r["date"] for r in existing}
    truly_new = [r["date"] for r in new_records if r["date"] not in old_dates]
    
    if added > 0 or not existing:
        write_json_safe(fp, {"code": code, "name": name, "records": merged})
        updated_count += 1
        updated_codes.append(code)
        new_dates.update(truly_new)
        progress = f"+{added}条"
    else:
        skip_count += 1
        progress = "持平"
    
    print(f"  [{i+1:>3d}/{total}] {code} {name[:12]:<12s} {old_last}→{new_last} {progress}")

print()
print(f"{'='*50}")
print(f"日线更新完成:")
print(f"  更新: {updated_count}只")
print(f"  无变化: {skip_count}只")
print(f"  错误: {error_count}只")
if new_dates:
    print(f"  新日期: {sorted(new_dates)}")
print(f"{'='*50}")

# === Sync Weekly ===
if updated_count > 0:
    print(f"\n📊 同步周线...")
    wk_updated = 0
    wk_skipped = 0
    for code in updated_codes:
        name = pool_codes[code]
        daily_fp = HISTORY / f"{code}.json"
        raw = load_json_safe(daily_fp)
        records = get_records(raw)
        if not records:
            continue
        weekly = daily_to_weekly(records)
        v2_fp = LONG_V2 / f"{code}.json"
        
        changed = True
        if v2_fp.exists():
            old_v2 = load_json_safe(v2_fp)
            old_recs = get_records(old_v2)
            if len(old_recs) == len(weekly) and old_recs and weekly:
                if old_recs[-1].get("date") == weekly[-1].get("date"):
                    changed = False
        
        if changed:
            write_json_safe(v2_fp, {"code": code, "name": name, "update": records[-1]["date"], "records": weekly})
            wk_updated += 1
        else:
            wk_skipped += 1
        if (updated_codes.index(code) + 1) % 50 == 0:
            print(f"  周线同步: [{updated_codes.index(code)+1}/{len(updated_codes)}] ...")
    
    print(f"  周线更新: {wk_updated}个, 未变: {wk_skipped}个")

print(f"\n✅ 全部完成 ({datetime.now().strftime('%H:%M')})")
print(f"日线: {HISTORY}")
print(f"周线: {LONG_V2}")
