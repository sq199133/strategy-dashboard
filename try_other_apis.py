#!/usr/bin/env python3
"""Try alternative data sources for really old ETFs (2011-era listings)."""
import json, time, random, requests
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
OLD_CODES = {
    "159905": "红利ETF工银",   # Listed ~2011
    "510170": "大宗商品ETF国联安",  # Listed ~2011
    "159928": "消费ETF汇添富",  # Listed 2013
    "159949": "创业板50ETF华安",  # Listed 2016
    "518880": "黄金ETF华夏",   # Listed 2013
    "512200": "房地产ETF南方",  # Listed 2017
    "512800": "银行ETF华宝",   # Listed 2017
    "512400": "有色金属ETF南方", # Listed 2017
}

print("1. 重试AKShare...")
try:
    import akshare as ak
    for code in ["159905", "510170", "159928"]:
        time.sleep(1)
        try:
            df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date="20100101", end_date="20260615", adjust="")
            print(f"  {code}: {len(df)}行, 日期{df.iloc[0]['日期']}~{df.iloc[-1]['日期']}")
        except Exception as e:
            print(f"  {code}: ❌ {str(e)[:60]}")
except ImportError:
    print("  未安装AKShare")

print("\n2. 尝试163API（换URL格式）...")
# Try different 163 URL format
urls = [
    (f"https://quotes.money.163.com/service/chddata.html?code=1159905&start=20100101&end=20260615",
     "标准格式 159905"),
    (f"https://quotes.money.163.com/service/chddata.html?code=0510170&start=20100101&end=20260615",
     "标准格式 510170"),
]
for url, label in urls:
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.text) > 200:
            lines = r.text.strip().split("\n")
            print(f"  {label}: {len(lines)}行 ✅")
            print(f"    首行: {lines[0]}")
            print(f"    次行: {lines[1][:80]}")
            print(f"    末行: {lines[-1][:80]}")
        else:
            print(f"  {label}: HTTP {r.status_code}, len={len(r.text)}")
    except Exception as e:
        print(f"  {label}: ❌ {str(e)[:60]}")

print("\n3. 尝试新浪旧版API（vip子域名）...")
# Try the VIP Sina API which might have different limits
url_vip = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz159905&scale=240&datalen=3000"
try:
    r = requests.get(url_vip, timeout=15)
    if r.status_code == 200 and len(r.text) > 100:
        data = r.json()
        if data:
            print(f"  VIP API sz159905: {len(data)}条 ✅")
            print(f"    首: {data[0]}")
            print(f"    末: {data[-1]}")
        else:
            print(f"  VIP API: 空数据")
    else:
        print(f"  VIP API: HTTP {r.status_code}, len={len(r.text)}")
except Exception as e:
    print(f"  VIP API: ❌ {str(e)[:60]}")

print("\n4. 使用新浪日线分段下载（分两段：早+晚）...")
# Try Sina with different code formats
for base_url in [
    "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData",
    "https://quotes.money.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
]:
    for sym in ["sz159905", "sh510170"]:
        url = f"{base_url}?symbol={sym}&scale=240&datalen=2000"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and len(r.text) > 100:
                data = r.json()
                if data and isinstance(data, list) and len(data) > 10:
                    print(f"  {base_url.split('/')[-2]} {sym}: {len(data)}条, 首{data[0]['day'][:10]} 末{data[-1]['day'][:10]}")
                    break
        except:
            pass

# Last resort: download from sina using the older format that might support page
print("\n5. 尝试biz.finance.sina.com.cn...")
url_sina2 = "https://biz.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz159905&scale=240&datalen=3000"
try:
    r = requests.get(url_sina2, timeout=15, headers={"Referer": "https://finance.sina.com.cn"})
    if r.status_code == 200 and len(r.text) > 100:
        data = r.json()
        if data and isinstance(data, list):
            print(f"  biz.sina sz159905: {len(data)}条, 首{data[0]['day'][:10]} 末{data[-1]['day'][:10]}")
        else:
            print(f"  biz.sina: 空或格式异常")
    else:
        print(f"  biz.sina: HTTP {r.status_code}")
except Exception as e:
    print(f"  biz.sina: ❌ {str(e)[:60]}")
