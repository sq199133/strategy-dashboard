#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 1: Standardize history_long_v2 format (list → dict)
Step 2: Generate weekly for missing old LOFs from daily data
Step 3: Verify
"""
import json
from pathlib import Path
import datetime
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")
HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = json.loads((Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
                   .read_text(encoding="utf-8")))
etf_map = {e["code"]: e for e in POOL["data"]}

def read_json_safe(fp):
    """Auto-detect encoding. Returns (data, had_encoding_issue)."""
    raw = fp.read_bytes()
    if len(raw) == 0:
        return None
    
    last_error = None
    for enc in ["utf-8", "gbk", "gb18030"]:
        try:
            text = raw.decode(enc)
            data = json.loads(text)
            return (data, enc != "utf-8")  # (data, needs_reencode)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            last_error = e
            continue
    raise RuntimeError(f"Cannot decode {fp.name}: {last_error}")

def write_json_safe(fp, data):
    """Write with UTF-8, sanitize problematic chars."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    fp.write_text(text, encoding="utf-8")

def daily_to_weekly(daily_records):
    """Aggregate daily records to weekly (Friday-based)."""
    if not daily_records:
        return []
    
    weekly = []
    week_data = []
    
    for i, r in enumerate(daily_records):
        dt = datetime.datetime.strptime(r["date"], "%Y-%m-%d").date()
        iso_yr, iso_wk, iso_dow = dt.isocalendar()
        
        week_data.append(r)
        
        # Friday (weekday=4) or last record
        if dt.weekday() == 4 or i == len(daily_records) - 1:
            close_p = float(r["close"])
            open_p = float(week_data[0].get("open", close_p))
            high_p = float(max(x.get("high", close_p) for x in week_data))
            low_p = float(min(x.get("low", close_p) for x in week_data))
            vol = sum(float(x.get("vol", 0)) for x in week_data)
            
            rec = {"w": f"{iso_yr}-W{iso_wk:02d}", "date": r["date"], "close": round(close_p, 4)}
            
            # Some LOFs only have date+close; add extra fields only if present
            if "open" in week_data[0]:
                rec["open"] = round(open_p, 4)
            if "high" in week_data[0]:
                rec["high"] = round(high_p, 4)
            if "low" in week_data[0]:
                rec["low"] = round(low_p, 4)
            if "vol" in week_data[0] or any("vol" in x for x in week_data):
                rec["vol"] = round(vol, 0)
            
            weekly.append(rec)
            week_data = []
    
    return weekly

# ---- Step 1: Standardize format ----
print("=" * 65)
print("Step 1: 格式标准化 + 编码统一 (GBK→UTF-8)")
print("=" * 65)

converted = 0      # list → dict
reencoded = 0      # GBK files rewritten as UTF-8
skipped = 0        # already good
regen_from_daily = 0  # empty files regenerated

for fp in sorted(LONG_V2.glob("*.json")):
    code = fp.stem
    result = read_json_safe(fp)
    
    if result is None:
        # Empty file - regenerate from daily
        print(f"  ⚠ {code}: 空文件，从日线重新生成")
        hist_fp = HISTORY / f"{code}.json"
        raw_hist = read_json_safe(hist_fp)
        if raw_hist:
            daily = raw_hist[0].get("records", [])
            weekly = daily_to_weekly(daily)
            name = etf_map.get(code, {}).get("name", "")
            write_json_safe(fp, {
                "code": code, "name": name,
                "update": weekly[-1]["date"] if weekly else "",
                "records": weekly
            })
            print(f"     → 周线{len(weekly)}条")
            regen_from_daily += 1
        continue
    
    raw, needs_reencode = result
    
    if isinstance(raw, dict) and "code" in raw and "records" in raw:
        if needs_reencode:
            write_json_safe(fp, raw)
            reencoded += 1
        else:
            skipped += 1
        continue
    
    # Convert list to standard dict
    records = raw if isinstance(raw, list) else raw.get("records", [])
    name = etf_map.get(code, {}).get("name", "")
    
    if not records:
        continue
    
    update_date = records[-1]["date"] if isinstance(records[-1], dict) and "date" in records[-1] else ""
    
    write_json_safe(fp, {
        "code": code, "name": name,
        "update": update_date, "records": records
    })
    converted += 1

print(f"  格式转换(list→dict): {converted}个")
print(f"  编码修复(GBK→UTF-8): {reencoded}个")
print(f"  日线重新生成: {regen_from_daily}个")
print(f"  无需处理: {skipped}个")

# ---- Step 2: Generate weekly for missing old LOFs ----
print(f"\n{'=' * 65}")
print("Step 2: 补缺失老LOF周线（从日线生成）")
print("=" * 65)

missing_old = ["501018", "501225", "501312"]
missing_new = ["159107", "159108", "159141", "159259", "520870", "530380", "530530",
               "560120", "560160", "560570", "560710", "563230", "589720"]

generated = 0
for code in missing_old + missing_new:
    hist_fp = HISTORY / f"{code}.json"
    v2_fp = LONG_V2 / f"{code}.json"
    
    if not hist_fp.exists():
        continue
    if v2_fp.exists():
        continue
    
    hist_raw = read_json_safe(hist_fp)
    if not hist_raw:
        continue
    daily_records = hist_raw[0].get("records", [])
    if not daily_records:
        continue
    
    weekly = daily_to_weekly(daily_records)
    if not weekly:
        continue
    
    name = etf_map.get(code, {}).get("name", "")
    write_json_safe(v2_fp, {
        "code": code, "name": name,
        "update": weekly[-1]["date"],
        "records": weekly
    })
    print(f"  {code} {name}: 日线{len(daily_records)}条 → 周线{len(weekly)}条 ({weekly[0]['date']}~{weekly[-1]['date']})")
    generated += 1

print(f"\n  新生成周线: {generated}个文件")

# ---- Step 3: Final stats ----
print(f"\n{'=' * 65}")
print("Step 3: 最终统计")
print("=" * 65)

files = sorted(LONG_V2.glob("*.json"))
total_rows = 0
pool_in_v2 = 0
for fp in files:
    d = read_json_safe(fp)
    if d is None:
        continue
    recs = d[0].get("records", [])
    total_rows += len(recs)
    code = d[0].get("code", fp.stem)
    if code in etf_map:
        pool_in_v2 += 1

missing_final = sorted(set(etf_map.keys()) - {f.stem for f in files})
print(f"  文件总数: {len(files)}")
print(f"  池中覆盖: {pool_in_v2}/{len(etf_map)}")
print(f"  总行数: {total_rows:,}")
print(f"  仍缺失: {len(missing_final)}只")
for code in missing_final:
    e = etf_map.get(code, {})
    print(f"    {code} {e.get('name','')}")

# Verify format on sample files
print(f"\n{'=' * 65}")
print("格式验证")
print("=" * 65)
for fn in ["159206.json", "159902.json", "159792.json", "510050.json"]:
    fp = LONG_V2 / fn
    if fp.exists():
        d = read_json_safe(fp)
        if d:
            d = d[0]
            print(f"  {fn}: code={d['code']}, name={d['name']}, records={len(d['records'])}条 ({d['records'][0]['date']}~{d['records'][-1]['date']})")
        else:
            print(f"  {fn}: EMPTY (still!)")

print(f"\n✅ 完成")
