#!/usr/bin/env python3
"""Clean up sz-prefix files - they are duplicates."""
import json
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")

for fp in sorted(HISTORY.glob("sz*.json")):
    base_code = fp.stem[2:]
    base_fp = HISTORY / f"{base_code}.json"
    if base_fp.exists():
        fp.unlink()
        print(f"  已删: {fp.name}")

print("\n✅ 清理完成")

left = list(HISTORY.glob("sz*.json"))
print(f"剩余sz前缀文件: {len(left)}个")
for f in sorted(left):
    print(f"  {f.name}")
