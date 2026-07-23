#!/usr/bin/env python3
"""Restore full OHLCV for 14 trimmed ETFs using multi-step Sina download."""
import json, time, random, requests
from datetime import datetime, date
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")

TRIM_CODES = {
    "159905": "红利ETF工银",
    "159928": "消费ETF汇添富",
    "159949": "创业板50ETF华安",
    "510170": "大宗商品ETF国联安",
    "511380": "可转债ETF博时 T+0",
    "512200": "房地产ETF南方",
    "512390": "中国低波ETF平安",
    "512400": "有色金属ETF南方",
    "512800": "银行ETF华宝",
    "512890": "红利低波ETF华泰柏瑞",
    "515300": "300红利低波ETF嘉实",
    "515450": "红利低波50ETF南方",
    "515750": "科技50ETF富国",
    "518880": "黄金ETF华夏",
}

def code_market(code):
    return "sh" if str(code).startswith(("6", "5")) else "sz"

def download_sina_batch(market, code, datalen):
    """Download from Sina, returns list of records or None."""
    url = (f"https://quotes.sina.cn/cn/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&datalen={datalen}")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or len(r.text) < 10:
            return None
        js = r.json()
        if not js or not isinstance(js, list):
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
    except Exception:
        return None

# For very old ETFs, try fetching multiple segments
# Sina API max is ~1600 for daily. Let me try:
# 1. Today + datalen=1600 → gets ~2020 to today
# 2. Then try monthly scale to get_older_data

def download_sina_monthly(market, code):
    """Download monthly data for long history."""
    url = (f"https://quotes.sina.cn/cn/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={market}{code}&scale=3200&datalen=800")
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
            })
        records.sort(key=lambda r: r["date"])
        return records
    except Exception:
        return None

def safestitch_daily_records(early_monthly, recent_daily):
    """Merge monthly (for old history) and daily (for recent). Keep daily for overlap."""
    by_date = {}
    for r in early_monthly:
        by_date[r["date"]] = r
    for r in recent_daily:
        by_date[r["date"]] = r
    return sorted(by_date.values(), key=lambda x: x["date"])

print(f"恢复 {len(TRIM_CODES)} 只被截断ETF的完整历史...\n")

for i, (code, name) in enumerate(TRIM_CODES.items()):
    market = code_market(code)
    short_name = name[:16]
    time.sleep(random.uniform(0.4, 0.8))
    
    # Step 1: Download max daily data
    daily = download_sina_batch(market, code, 1600)
    if daily is None or len(daily) == 0:
        print(f"  [{i+1}/{len(TRIM_CODES)}] {code} {short_name:<16s} ✗ 日线下载失败")
        continue
    
    d_start = daily[0]["date"]
    d_end = daily[-1]["date"]
    
    # Step 2: If start date > 2019, try monthly to get older data
    daily_year = int(d_start[:4])
    monthly = None
    if daily_year > 2019:
        time.sleep(random.uniform(0.3, 0.5))
        monthly = download_sina_monthly(market, code)
    
    if monthly and monthly[0]["date"] < daily[0]["date"]:
        # Stitch: monthly (old) + daily (recent)
        all_recs = safestitch_daily_records(monthly, daily)
        m_start = monthly[0]["date"]
        print(f"  [{i+1}/{len(TRIM_CODES)}] {code} {short_name:<16s} "
              f"月线{m_start}+日线{d_start}→{d_end} = {len(all_recs)}条 ✅", end="")
    else:
        all_recs = daily
        print(f"  [{i+1}/{len(TRIM_CODES)}] {code} {short_name:<16s} "
              f"日线{d_start}→{d_end} = {len(all_recs)}条 ✅", end="")
    
    # Save
    (HISTORY / f"{code}.json").write_text(
        json.dumps({"code": code, "name": name, "records": all_recs},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    
    # Check field integrity
    full = sum(1 for r in all_recs if "open" in r)
    print(f" (全字段:{full}/{len(all_recs)})", end="")
    
    # Weekly sync
    weekly = []
    week_data = []
    for j, r in enumerate(all_recs):
        dt_obj = datetime.strptime(r["date"], "%Y-%m-%d").date()
        week_data.append(r)
        if dt_obj.weekday() == 4 or j == len(all_recs) - 1:
            close_p = float(r["close"])
            open_p = float(week_data[0].get("open", close_p))
            high_p = float(max(x.get("high", close_p) for x in week_data))
            low_p = float(min(x.get("low", close_p) for x in week_data))
            vol = sum(float(x.get("vol", 0)) for x in week_data)
            rec_w = {"w": f"{dt_obj.isocalendar()[0]}-W{dt_obj.isocalendar()[1]:02d}",
                     "date": r["date"], "close": round(close_p, 4)}
            if "open" in week_data[0]:
                rec_w["open"] = round(open_p, 4)
            if "high" in week_data[0]:
                rec_w["high"] = round(high_p, 4)
            if "low" in week_data[0]:
                rec_w["low"] = round(low_p, 4)
            if "vol" in week_data[0] or any("vol" in x for x in week_data):
                rec_w["vol"] = round(vol, 0)
            weekly.append(rec_w)
            week_data = []
    
    (LONG_V2 / f"{code}.json").write_text(
        json.dumps({"code": code, "name": name, "update": all_recs[-1]["date"], "records": weekly},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    print(f" 周线:{len(weekly)}条")

print(f"\n✅ 恢复完成")
