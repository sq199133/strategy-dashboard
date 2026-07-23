# -*- coding: utf-8 -*-
"""
金山文档 ksheet 读取工具（编码修复版）
直接调用 mcporter 捕获原始字节，用 UTF-8 解码，绕过 PowerShell 的 GBK 乱码问题。
"""
import subprocess
import json
import sys
from collections import defaultdict

MCPORTER = r"C:\Users\沈强\AppData\Roaming\QClaw\npm-global\mcporter.cmd"

def read_sheet(file_id, sheet_name=None, max_rows=50):
    args = {}
    if sheet_name:
        args["sheet_name"] = sheet_name
    cmd = [
        MCPORTER, "call", "kdocs-qclaw", "read_file",
        f"file_id={file_id}",
        "--args", json.dumps(args, ensure_ascii=False),
    ]
    proc = subprocess.run(cmd, capture_output=True, shell=True)
    raw = proc.stdout

    # 探测编码：优先 utf-8，失败回退 gbk
    text = None
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    data = json.loads(text, strict=False)
    content = data.get("data", {}).get("content", {})
    rd = content.get("range_data", {}).get("detail", {}).get("rangeData", [])

    rows = defaultdict(dict)
    for c in rd:
        rows[c["rowFrom"]][c["colFrom"]] = c.get("cellText", "")
    return rows

if __name__ == "__main__":
    fid = sys.argv[1] if len(sys.argv) > 1 else "pg1M6VbERxMqL5rD12mJrxfWeTUWv4g2z"
    sheet = sys.argv[2] if len(sys.argv) > 2 else "周线动能策略"
    rows = read_sheet(fid, sheet)
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    for ri in sorted(rows)[:n]:
        cols = rows[ri]
        if not cols:
            continue
        maxc = max(cols)
        line = " | ".join(str(cols.get(ci, "")) for ci in range(maxc + 1))
        print(line)
