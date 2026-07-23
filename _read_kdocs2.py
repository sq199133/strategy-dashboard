# -*- coding: utf-8 -*-
"""读取金山文档持仓，输出到文件"""
import subprocess, json, sys, os

MCP = r"C:\Users\沈强\AppData\Roaming\QClaw\npm-global\mcporter.cmd"
FILE_ID = "pg1M6VbERxMqL5rD12mJrxfWeTUWv4g2"
OUT = r"D:\Qclaw_Trading\_kdocs_out.json"

args_list = json.dumps({"file_id": FILE_ID}, ensure_ascii=False)
r = subprocess.run(
    [MCP, "call", "kdocs-qclaw", "sheet.list_tables", "--args", args_list],
    capture_output=True, timeout=15, shell=True
)
print("rc:", r.returncode)
if r.stdout:
    with open(OUT, "wb") as f:
        f.write(r.stdout)
    print("saved to", OUT)
if r.stderr:
    print("stderr:", r.stderr[:200])
