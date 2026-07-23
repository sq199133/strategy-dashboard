#!/usr/bin/env python3
"""Convert all old list-format ETF data files to standard dict format."""
import json
from pathlib import Path
from datetime import datetime

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
pool = json.loads(POOL.read_text(encoding="utf-8"))
etf_map = {e["code"]: e for e in pool["data"]}

converted = 0
skipped = 0
errors = []

for fp in sorted(HISTORY.glob("*.json")):
    if fp.name.startswith("_"):
        continue  # 守护文件
    
    try:
        raw = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append((fp.name, f"解析失败: {e}"))
        continue
    
    # 已经是 dict 格式且有 records 字段 → 跳过
    if isinstance(raw, dict):
        if "records" in raw:
            skipped += 1
            continue
        # 有些 dict 没有 records 但有 code/name → 可能是部分转换的
        if "records" not in raw and "code" in raw:
            skipped += 1
            continue
    
    # list 格式 → 转 dict
    if isinstance(raw, list):
        records = []
        for r in raw:
            rec = {
                "date": r.get("date") or r.get("day", ""),
                "open": float(r.get("open", 0)),
                "close": float(r.get("close", 0)),
                "high": float(r.get("high", 0)),
                "low": float(r.get("low", 0)),
                "vol": int(float(r.get("vol") or r.get("volume", 0))),
                "amount": int(float(r.get("amount", 0))),
                "chg": float(r.get("chg", r.get("change_pct", 0)))
            }
            records.append(rec)
        
        records.sort(key=lambda r: r["date"])
        
        code = fp.stem
        name = etf_map.get(code, {}).get("name", fp.stem)
        out = {"code": code, "name": name, "records": records}
        
        fp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        converted += 1

# 报告
print(f"转换完成: {converted} 个文件")
print(f"已跳过:   {skipped} 个文件（已是标准格式）")
if errors:
    print(f"错误:     {len(errors)} 个")
    for fn, err in errors:
        print(f"  {fn}: {err}")

# 验证
print(f"\n验证...")
list_count = 0
dict_count = 0
for fp in sorted(HISTORY.glob("*.json")):
    if fp.name.startswith("_"):
        continue
    try:
        d = json.loads(fp.read_text(encoding="utf-8"))
        if isinstance(d, list):
            list_count += 1
        else:
            dict_count += 1
    except:
        pass

print(f"最终格式: dict={dict_count}, list={list_count}")
if list_count == 0:
    print("✅ 全部统一为标准 dict 格式")
else:
    print(f"⚠ 仍有 {list_count} 个文件为 list 格式")
