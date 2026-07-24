"""重试27只漏更新的标的（优先Sina，Tencent兜底）"""
import json, urllib.request, requests, time, random
from pathlib import Path

H = Path("D:/QClaw_Trading/data/history")
targets = ["160216","160719","160723","161128","161130","162411","162415","162719",
           "561380","561510","561910","562500","562800","563220","563230","563300","563800",
           "588000","588020","588030","588080","588140","588170","588200","588220","588750","589000"]

def mkt(code):
    if code.startswith(("16","159")): return "sz"
    return "sh"

def download_sina(code):
    url = f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData?symbol={mkt(code)}{code}&scale=240&datalen=1500"
    r = requests.get(url, timeout=15)
    if r.status_code == 200 and len(r.text) > 20:
        data = r.json()
        records = [{"date":d["day"],"open":float(d["open"]),"close":float(d["close"]),
                     "high":float(d["high"]),"low":float(d["low"]),"vol":int(float(d["volume"])),
                     "amount":0} for d in data]
        records.sort(key=lambda x:x["date"])
        return records
    return None

def download_tencent(code):
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt(code)}{code},day,,,2000,"
    resp = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=20)
    j = json.loads(resp.read().decode("utf-8"))
    dd = j.get("data",{})
    rows = dd.get(f"{mkt(code)}{code}",{}).get("day")
    if not rows: return None
    records = [{"date":r[0],"open":float(r[1]),"close":float(r[2]),"high":float(r[3]),"low":float(r[4]),
                 "vol":int(float(r[5])),"amount":0} for r in rows]
    records.sort(key=lambda x:x["date"])
    return records

succ = 0
fail = 0
for i, code in enumerate(targets):
    fp = H / f"{code}.json"
    r = download_sina(code)
    if r is None:
        r = download_tencent(code)
    if r is None:
        print(f"  [{i+1}/{len(targets)}] {code}: 双源均失败")
        fail += 1
        continue
    fp.write_text(json.dumps({"code":code,"name":"","records":r}, ensure_ascii=False), encoding="utf-8")
    print(f"  [{i+1}/{len(targets)}] {code}: {len(r)}条, {r[0]['date']}~{r[-1]['date']}")
    succ += 1
    time.sleep(random.uniform(0.3,0.8))
print(f"\n成功{succ}, 失败{fail}")
