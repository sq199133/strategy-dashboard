#!/usr/bin/env python3
"""
全量ETF前复权修复脚本：
1. 扫描所有ETF文件，检测除权/除息事件（日涨跌>|40%|）
2. 计算调整因子（前复权）
3. 修正所有OHLC价格，保持价格序列连续
4. 元数据存储在 records 中，可追溯还原
"""
import json, copy
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")

def detect_adjustments(records):
    """Detect ex-right/split events by extreme daily returns."""
    events = []
    for i in range(1, len(records)):
        pc = float(records[i-1]["close"])
        cc = float(records[i]["close"])
        if pc <= 0:
            continue
        ret = (cc - pc) / pc
        if abs(ret) > 0.40:
            events.append({
                "date": records[i]["date"],
                "idx": i,
                "factor": cc / pc,
                "ret_pct": round(ret * 100, 1),
                "prev_close": round(pc, 4),
                "new_close": round(cc, 4)
            })
    return events

def apply_adj(records, events):
    """Apply forward adjustment: multiply prices before each event by factor."""
    adj_records = copy.deepcopy(records)
    if not events:
        return adj_records, []
    
    # Sort events by date ascending, compute cumulative factors
    events_sorted = sorted(events, key=lambda e: e["date"])
    
    # Build cumulative factor array: cum_factor[i] = product of factors for events at or before i
    n = len(adj_records)
    cum_factors = [1.0] * n
    
    for ev in events_sorted:
        idx = ev["idx"]
        factor = ev["factor"]
        # All records BEFORE this event get multiplied by factor
        for j in range(idx):
            cum_factors[j] *= factor
    
    # Apply adjustments
    for i, rec in enumerate(adj_records):
        cf = cum_factors[i]
        if cf != 1.0:
            rec["open"] = round(float(rec.get("open", rec["close"])) * cf, 4)
            rec["high"] = round(float(rec.get("high", rec["close"])) * cf, 4)
            rec["low"] = round(float(rec.get("low", rec["close"])) * cf, 4)
            rec["close"] = round(float(rec["close"]) * cf, 4)
    
    return adj_records, events_sorted

def save(fp, raw_data, adj_records, adjustments):
    """Save with adjustment metadata."""
    out = dict(raw_data)
    out["records"] = adj_records
    if adjustments:
        out["adjustments"] = [{
            "date": e["date"],
            "factor": round(e["factor"], 6),
            "ret_pct": e["ret_pct"],
            "prev_close_raw": e["prev_close"],
            "new_close_raw": e["new_close"]
        } for e in adjustments]
    fp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

# === Main ===
all_files = sorted([fp for fp in HISTORY.glob("*.json") if not fp.stem.startswith("_")])
print(f"扫描 {len(all_files)} 个文件...\n")

fixed = 0
fixed_events = 0

for fp in all_files:
    code = fp.stem
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", [])
    if not recs:
        continue
    
    events = detect_adjustments(recs)
    if not events:
        continue
    
    adj_recs, adj_events = apply_adj(recs, events)
    
    # Verify: re-detect should find no events
    re_detect = detect_adjustments(adj_recs)
    
    save(fp, raw, adj_recs, adj_events)
    fixed += 1
    fixed_events += len(adj_events)
    
    name = raw.get("name", "")[:16]
    event_str = "; ".join([f'{e["date"]} {e["ret_pct"]:+.1f}%(f={e["factor"]:.3f})' for e in adj_events])
    clean_str = f" ✅ 修复后0事件" if not re_detect else f" ⚠ 仍有{len(re_detect)}个异常(阈值40%)"
    print(f"  {code} {name:<16s}: {event_str}{clean_str}")

print(f"\n✅ 修复: {fixed}个文件, {fixed_events}个除权事件")

if fixed > 0:
    # Also regenerate weekly
    print(f"\n同步周线（前复权后）...")
    wk = 0
    for fp in all_files:
        code = fp.stem
        raw = json.loads(fp.read_text(encoding="utf-8"))
        recs = raw.get("records", [])
        if not recs:
            continue
        
        weekly = []
        wd = []
        for j, r in enumerate(recs):
            from datetime import datetime
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            wd.append(r)
            if d.weekday() == 4 or j == len(recs) - 1:
                cp = float(r["close"])
                weekly.append({
                    "w": f'{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}',
                    "date": r["date"],
                    "close": round(cp, 4),
                    "open": round(float(wd[0].get("open", cp)), 4),
                    "high": round(max(float(x.get("high", cp)) for x in wd), 4),
                    "low": round(min(float(x.get("low", cp)) for x in wd), 4),
                    "vol": sum(float(x.get("vol", 0)) for x in wd),
                })
                wd = []
        
        (LONG_V2 / f"{code}.json").write_text(
            json.dumps({"code": code, "name": raw.get("name",""), "records": weekly,
                        "update": recs[-1]["date"] if recs else ""},
                       ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        wk += 1
    print(f"周线: {wk}个同步")

# Final audit
print(f"\n=== 最终审计（验证0异常） ===")
remaining = 0
for fp in all_files:
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", [])
    for i in range(1, len(recs)):
        pc = float(recs[i-1]["close"])
        cc = float(recs[i]["close"])
        if pc > 0 and abs((cc-pc)/pc*100) > 40:
            remaining += 1
            if remaining <= 5:
                print(f"  ⚠ {fp.stem} {recs[i]['date']} {(cc-pc)/pc*100:+.1f}%")
if remaining == 0:
    print(f"  ✅ 全部消除，0个>40%异常")
else:
    print(f"  ⚠ 剩余{remaining}个异常（可能阈值外因素）")
