#!/usr/bin/env python3
"""Check latest available data date."""
import json, requests, datetime

today = datetime.datetime.now().strftime("%Y-%m-%d")
now = datetime.datetime.now()
print(f"当前时间: {today} {now.strftime('%H:%M')}")
print(f"周几: {now.weekday()} (0=周一)")

# Check Sina for 510050
url = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh510050&scale=240&datalen=5"
r = requests.get(url, timeout=15)
data = r.json()
print(f"\n510050 最近5条:")
for row in data:
    print(f"  {row['day']}  O:{row['open']} H:{row['high']} L:{row['low']} C:{row['close']} V:{row['volume']}")

last = data[-1]
last_date = last["day"].split()[0]
print(f"\n最新数据日期: {last_date}")
diff = (datetime.datetime.strptime(today, "%Y-%m-%d") - datetime.datetime.strptime(last_date, "%Y-%m-%d")).days
print(f"与今天({today})差值: {diff} 天")

# Check if there's actually new data
local_path = "D:/QClaw_Trading/data/history/510050.json"
local = json.loads(open(local_path, encoding="utf-8").read())
local_recs = local["records"]
local_last = local_recs[-1]["date"]
print(f"\n本地最后日期: {local_last}")
print(f"需要更新: {last_date != local_last}")
print(f"新增记录数: {len(data) - sum(1 for d in data if d['day'].split()[0] in {r['date'] for r in local_recs})}")
