import json

# Check weekly scan file structure
with open(r'D:\QClaw_Trading\scan_results\weekly_scan_v4_20260717_220328.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print(f"Type: {type(d)}")
print(f"Keys: {list(d.keys())[:10] if isinstance(d, dict) else 'N/A'}")
if isinstance(d, dict):
    first_key = list(d.keys())[0]
    print(f"First key: {first_key}")
    print(f"First value type: {type(d[first_key])}")
    print(f"First value sample: {str(d[first_key])[:200]}")
elif isinstance(d, list):
    print(f"List len: {len(d)}")
    print(f"First item: {str(d[0])[:200]}")
