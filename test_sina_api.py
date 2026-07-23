#!/usr/bin/env python3
"""Test Sina daily kline limits."""
import requests, json

code = "512880"
for dl in [500, 1000, 1500, 2000, 3000, 5000]:
    url = f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh{code}&scale=240&datalen={dl}"
    r = requests.get(url, timeout=15)
    if r.status_code == 200 and r.text.strip() and len(r.text) > 10:
        try:
            data = json.loads(r.text)
            if data:
                print(f"datalen={dl}: {len(data)} rec, first={data[0]['day']} last={data[-1]['day']}")
            else:
                print(f"datalen={dl}: empty")
        except:
            print(f"datalen={dl}: json err, text={r.text[:50]}")
    else:
        print(f"datalen={dl}: {r.status_code}, {len(r.text)} bytes, {r.text[:50]}")
