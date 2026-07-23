"""补000300指数至2026-07-23"""
import json, urllib.request
from pathlib import Path

fp = Path("D:/QClaw_Trading/data/history/000300.json")
fp.parent.mkdir(parents=True, exist_ok=True)

# baostock
url = "https://baostock.com/baostock/index.php/DataAPI/kline"
# 用 baostock SDK 最可靠，但没安装就直接 post
import urllib.parse
data = urllib.parse.urlencode({
    "code": "sh.000300",
    "fields": "date,open,high,low,close,volume,amount",
    "start": "2020-01-01",
    "end": "2026-07-23",
    "frequency": "d",
    "adjustflag": "2"
}).encode()
try:
    req = urllib.request.Request("https://baostock.com/baostock/index.php/DataAPI/kline", data=data,
                                  headers={"User-Agent":"Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=30)
    html = resp.read().decode("utf-8")
except Exception as e:
    print(f"baostock: {e}")
    # tencent 兜底
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,day,,,2000,"
    resp = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=20)
    j = json.loads(resp.read().decode("utf-8"))
    rows = j.get("data",{}).get("sh000300",{}).get("day",[])
    records = []
    for r in rows:
        records.append({"date":r[0],"open":float(r[1]),"close":float(r[2]),"high":float(r[3]),"low":float(r[4]),"vol":int(float(r[5])),"amount":0})
    records.sort(key=lambda x:x["date"])
    fp.write_text(json.dumps({"code":"000300","name":"沪深300","records":records}, ensure_ascii=False), encoding="utf-8")
    print(f"tencent: {len(records)}条, {records[0]['date']}~{records[-1]['date']}")
