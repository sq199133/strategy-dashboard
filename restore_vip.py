#!/usr/bin/env python3
"""
Full restoration of 14 trimmed ETFs using VIP Sina API (supports datalen=5000).
Restores complete OHLCV history from ETF listing date.
"""
import json, time, random, requests
from datetime import datetime
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

def download_vip_sina_full(code):
    """VIP Sina API with datalen=5000 for complete history."""
    market = code_market(code)
    url = (f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&datalen=5000")
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200 or len(r.text) < 10:
            return None
        data = r.json()
        if not data or not isinstance(data, list):
            return None
        records = []
        for row in data:
            day = row["day"].split()[0]
            records.append({
                "date": day,
                "open": float(row["open"]),
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "vol": int(float(row.get("volume", 0))),
                "amount": 0,
                "chg": 0.0
            })
        records.sort(key=lambda r: r["date"])
        return records
    except Exception as e:
        return None

def daily_to_weekly(all_recs):
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
    return weekly

print(f"VIP API完整恢复 {len(TRIM_CODES)} 只ETF...\n")

for i, (code, name) in enumerate(TRIM_CODES.items()):
    short_name = name[:16]
    time.sleep(random.uniform(0.4, 0.8))
    
    records = download_vip_sina_full(code)
    if records is None or len(records) < 100:
        print(f"  [{i+1}/{len(TRIM_CODES)}] {code} {short_name:<16s} ✗ 下载失败")
        continue
    
    # Save daily
    out = {"code": code, "name": name, "records": records}
    (HISTORY / f"{code}.json").write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    
    full = sum(1 for r in records if "open" in r)
    print(f"  [{i+1}/{len(TRIM_CODES)}] {code} {short_name:<16s} "
          f"{records[0]['date']}~{records[-1]['date']} = {len(records)}条 "
          f"(全字段:{full}/{len(records)})", end="")
    
    # Weekly
    weekly = daily_to_weekly(records)
    v2_out = {"code": code, "name": name, "update": records[-1]["date"], "records": weekly}
    (LONG_V2 / f"{code}.json").write_text(
        json.dumps(v2_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f" 周线:{len(weekly)}条")

print(f"\n✅ 恢复完成！运行最终检查...")

# Run check
import subprocess, sys
result = subprocess.run([sys.executable, "D:/QClaw_Trading/maintain_etf_data.py", "check"],
                       capture_output=True, text=True, cwd="D:/QClaw_Trading")
print(result.stdout)
