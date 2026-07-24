import urllib.request, json
from pathlib import Path
url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,day,,,2000,"
resp = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=20)
j = json.loads(resp.read().decode("utf-8"))
rows = j.get("data",{}).get("sh000300",{}).get("day",[])
records = [{"date":r[0],"open":float(r[1]),"close":float(r[2]),"high":float(r[3]),"low":float(r[4]),"vol":int(float(r[5])),"amount":0} for r in rows]
records.sort(key=lambda x:x["date"])
Path("D:/QClaw_Trading/data/history/000300.json").write_text(json.dumps({"code":"000300","name":"沪深300","records":records}, ensure_ascii=False), encoding="utf-8")
print(f"000300: {len(records)}条, {records[0]['date']}~{records[-1]['date']}")
