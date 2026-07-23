# -*- coding: utf-8 -*-
import json, urllib.request
from pathlib import Path

UA = {"User-Agent":"Mozilla/5.0","Referer":"http://finance.sina.com.cn"}
code = "159905"
ku = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sz{code}&scale=240&datalen=3"
klines = json.loads(urllib.request.urlopen(urllib.request.Request(ku,headers=UA),timeout=25).read().decode("utf-8"))
today = klines[-1]["day"].split()[0]
hf = Path(f"D:/QClaw_Trading/data/history/{code}.json")
with open(hf, encoding="utf-8") as f: obj = json.load(f)
vol_key = "vol" if b'"vol":' in open(hf,"rb").read() else "volume"
nr = {"date":today,"open":round(float(klines[-1]["open"]),4),"high":round(float(klines[-1]["high"]),4),
    "low":round(float(klines[-1]["low"]),4),"close":round(float(klines[-1]["close"]),4),
    vol_key:int(float(klines[-1].get("volume",0))),"amount":0,"chg":0.0}
obj["records"].append(nr); obj["update"]=today
with open(hf,"w",encoding="utf-8") as f:
    json.dump(obj,f,ensure_ascii=False,indent=None,separators=(",",":"))
print(f"+ {code} {today} C={nr['close']:.4f}")
