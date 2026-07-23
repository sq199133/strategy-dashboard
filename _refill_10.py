import json, time, urllib.request
from pathlib import Path

H = Path("D:/QClaw_Trading/data/history")

codes = ['513050','159605','513060','513660','513690','513880','513120','513850','513400','162415']

for code in codes:
    mkt = "sz" if code.startswith(("16","159")) else "sh"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,800,"
    resp = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=30)
    j = json.loads(resp.read().decode("utf-8"))
    rows = j.get("data",{}).get(f"{mkt}{code}",{}).get("day")
    if not rows:
        print(f"{code} ❌ 空")
        continue
    records = []
    for r in rows:
        records.append({"date":r[0],"open":float(r[1]),"close":float(r[2]),"high":float(r[3]),"low":float(r[4]),"vol":int(float(r[5])),"amount":0,"chg":0.0})
    records.sort(key=lambda r: r["date"])
    out = {"code":code,"name":"","records":records}
    H.joinpath(f"{code}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"{code} [OK] {len(records)}条 {records[0]['date']}~{records[-1]['date']}")
    time.sleep(1)
