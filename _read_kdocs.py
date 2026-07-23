# -*- coding: utf-8 -*-
"""读取金山文档持仓"""
import subprocess, json, sys, os, shutil

# 找mcporter
for p in [r"C:\Users\沈强\AppData\Roaming\QClaw\npm-global\mcporter.cmd",
          os.path.join(os.environ.get('APPDATA',''), "QClaw", "npm-global", "mcporter.cmd")]:
    if os.path.exists(p):
        MCP = p
        break
else:
    # 搜索
    appdata = os.environ.get('APPDATA', '')
    search = os.path.join(appdata, 'QClaw', 'npm-global', 'mcporter.cmd')
    MCP = search

print(f"mcporter path: {MCP}")
FILE_ID = "pg1M6VbERxMqL5rD12mJrxfWeTUWv4g2"

args_list = json.dumps({"file_id": FILE_ID}, ensure_ascii=False)
print(f"args: {args_list}")

# 运行
env = os.environ.copy()
r1 = subprocess.run([MCP, "call", "kdocs-qclaw", "sheet.list_tables",
                     "--args", args_list],
                    capture_output=True, timeout=15, shell=False, env=env)

print(f"returncode: {r1.returncode}")
print(f"stdout len: {len(r1.stdout)}")
print(f"stderr: {r1.stderr[:200]}")
if r1.stdout:
    try:
        d1 = json.loads(r1.stdout)
        print("JSON OK:", json.dumps(d1, ensure_ascii=False, indent=2)[:3000])
    except:
        print("stdout:", r1.stdout[:1000])
