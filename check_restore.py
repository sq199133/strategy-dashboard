#!/usr/bin/env python3
"""Identify the trimmed ETFs and try to restore full history."""
import json
from pathlib import Path
from datetime import datetime

HISTORY = Path("D:/QClaw_Trading/data/history")

# Step 1: Find which ones got trimmed (current records exactly 1500, but should have more)
print("=== 被截断的ETF确认 ===")
trimmed = []
for fp in sorted(HISTORY.glob("*.json")):
    if fp.stem == "_DATA_GUARDIAN_":
        continue
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", []) if isinstance(raw, dict) else []
    if len(recs) == 1500:
        # Check if this ETF was among the 53 fixed ones (should have more history)
        start_year = int(recs[0]["date"][:4])
        trimmed.append((fp.stem, raw.get("name", ""), start_year, recs[0]["date"]))
        print(f"  {fp.stem} {raw.get('name','')[:20]:<20s} 起点:{recs[0]['date']} 终点:{recs[-1]['date']}")

print(f"\n共{len(trimmed)}只被截断到1500条")

# Step 2: Try AKShare to get full history
print("\n=== 尝试AKShare获取历史数据 ===")
try:
    import akshare as ak
except ImportError:
    print("AKShare未安装，用网易API替代")

# Try Sina with different approach - use multiple calls to fill gaps
# First check: what's the earliest date we have for these?
# Let me try a different Sina API format that supports pagination

print("\n=== 尝试网易163行情API ===")

codes_netease = {
    "512400": "0512400",  # SH: 0 prefix
    "518880": "0518880",
    "512800": "0512800",
    "515450": "0515450",
    "515750": "0515750",
    "510170": "0510170",
    "512890": "0512890",
    "159949": "1159949",
    "515300": "0515300",
    "512200": "0512200",
    "159928": "1159928",
    "159905": "1159905",
}

import requests

test_code = "512400"
url = f"https://quotes.money.163.com/service/chddata.html?code={codes_netease['512400']}&start=20170101&end=20200101"
try:
    r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    print(f"  512400 网易API: status={r.status_code}, len={len(r.text)}")
    if r.status_code == 200 and len(r.text) > 100:
        lines = r.text.strip().split("\n")
        print(f"  行数: {len(lines)}")
        print(f"  首行: {lines[0]}")
        print(f"  第二行: {lines[1]}")
        print(f"  末行: {lines[-1]}")
        print(f"  末行: {lines[-2]}")
    else:
        print("  ❌ 网易API不可用")
except Exception as e:
    print(f"  ❌ 网易API错误: {e}")

# Try Sina raw data
print("\n=== 尝试Sina历史K线(Sina old format) ===")
# Try the older Sina historical API that gives all data
url2 = f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh512400&scale=240&datalen=1600"
try:
    r2 = requests.get(url2, timeout=15)
    data = r2.json()
    print(f"  Sina datalen=1600: {len(data)}条")
except Exception as e:
    print(f"  ❌: {e}")

# Check: Sina might support different datalen limits
for dl in [2000, 3000, 5000]:
    url3 = f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh512400&scale=240&datalen={dl}"
    try:
        r3 = requests.get(url3, timeout=15)
        data = r3.json()
        print(f"  Sina datalen={dl}: {len(data)}条")
        if len(data) < 200:
            break  # Hit the limit
    except Exception as e:
        print(f"  Sina datalen={dl}: Error - {str(e)[:50]}")
        break

# Check what akshare can do
print("\n=== 检查akshare的etf历史数据 ===")
try:
    import akshare as ak
    # Test with one ETF
    df = ak.fund_etf_hist_em(symbol="512400", period="daily", start_date="20170101", end_date="20260615", adjust="")
    print(f"  AKShare 512400: {len(df)}行")
    print(f"  列: {list(df.columns)}")
    print(f"  首行: {df.head(1).to_dict()}")
    print(f"  末行: {df.tail(1).to_dict()}")
except Exception as e:
    print(f"  AKShare error: {e}")
    print("  尝试另一个akshare函数...")
    try:
        df = ak.stock_zh_a_hist(symbol="512400", period="daily", start_date="20170101", end_date="20260615", adjust="")
        print(f"  stock_zh_a_hist 512400: {len(df)}行, 列: {list(df.columns)}")
    except Exception as e2:
        print(f"  也失败: {e2}")
