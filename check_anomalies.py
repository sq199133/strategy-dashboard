import json
from pathlib import Path

def check_around(code, target_date, days=5):
    fp = Path(f"D:/QClaw_Trading/data/history/{code}.json")
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", [])
    name = raw.get("name", "?")
    dates = [r["date"] for r in recs]
    if target_date not in dates:
        print(f"{code} {name}: {target_date} 不在记录中")
        return
    idx = dates.index(target_date)
    print(f"\n=== {code} {name} ===")
    for i in range(max(0, idx-3), min(len(recs), idx+4)):
        r = recs[i]
        chg = ""
        if i > 0:
            prev_c = float(recs[i-1]["close"])
            cur_c = float(r["close"])
            if prev_c > 0:
                chg = f"{(cur_c-prev_c)/prev_c*100:+.1f}%"
        print(f'  {r["date"]} O:{r["open"]} H:{r["high"]} L:{r["low"]} C:{r["close"]} V:{r["vol"]}  {chg}')

# Then scan all 312 files for extreme moves
print("=== 全量扫描: 日涨跌 >|40%| ===")
H = Path("D:/QClaw_Trading/data/history")
total_anomaly_codes = set()
anomaly_count = 0

for fp in sorted(H.glob("*.json")):
    if fp.stem.startswith("_"):
        continue
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", [])
    name = raw.get("name", "")[:16]
    for i in range(1, len(recs)):
        pc = float(recs[i-1]["close"])
        cc = float(recs[i]["close"])
        if pc > 0:
            cp = (cc - pc) / pc * 100
            if abs(cp) > 40:
                total_anomaly_codes.add(fp.stem)
                anomaly_count += 1
                if anomaly_count <= 30:
                    print(f'  {fp.stem} {name}: {recs[i]["date"]} {cp:+.1f}%')

print(f"\n合计: {len(total_anomaly_codes)}只ETF有异常, 共{anomaly_count}次极端涨跌")

# Check: was 2021-06-25 a dividend/rights date for 159928?
print(f"\n=== 模式分析 ===")
for code in sorted(total_anomaly_codes):
    fp = H / f"{code}.json"
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", [])
    name = raw.get("name", "")[:24]
    events = []
    for i in range(1, len(recs)):
        pc = float(recs[i-1]["close"])
        cc = float(recs[i]["close"])
        if pc > 0:
            cp = (cc - pc) / pc * 100
            if abs(cp) > 40:
                events.append((recs[i]["date"], cp))
    
    # Get prev/next around first event
    if events:
        dt = events[0][0]
        cp = events[0][1]
        dates = [r["date"] for r in recs]
        idx = dates.index(dt)
        prev_c = float(recs[idx-1]["close"]) if idx > 0 else 0
        cur_c = float(recs[idx]["close"])
        next_c = float(recs[idx+1]["close"]) if idx+1 < len(recs) else 0
        reb = (next_c - prev_c) / prev_c * 100 if prev_c > 0 else 0
        
        # Pattern: sharp drop followed by recovery next day = dividend adjustment
        pattern = "❓"
        if cp < -40 and abs(reb) < 5:
            pattern = "📉 单日暴跌(分红/除权?)"
        elif cp < -40:
            pattern = "📉 暴跌后反弹"
        elif cp > 40:
            pattern = "📈 单日暴涨(送股/复权?)"
        
        print(f'  {code} {name}: {dt} {cp:+.1f}% 恢复:{reb:+.1f}%  {pattern}')
