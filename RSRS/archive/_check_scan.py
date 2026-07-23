import json

# Check latest weekly scan for July 17 data
with open(r'D:\QClaw_Trading\scan_results\weekly_scan_v4_20260717_220328.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print(f"Timestamp: {d['ts']}")
print(f"RSRS signal keys: {list(d.get('target', {}).keys()) if isinstance(d.get('target'), dict) else d.get('target')}")
print(f"Target: {json.dumps(d.get('target', {}), ensure_ascii=False, indent=2)[:500]}")
print(f"\nBuy: {d.get('buy', {})}")
print(f"Sell: {d.get('sell', {})}")
print(f"Keep: {d.get('keep', {})}")
print(f"Qual: {d.get('qual', {})}")

# Also check the most recent scan file
import os
scan_dir = r'D:\QClaw_Trading\scan_results'
files = sorted([f for f in os.listdir(scan_dir) if f.endswith('.json')])
print(f"\nMost recent scan files:")
for f in files[-3:]:
    print(f"  {f}")
