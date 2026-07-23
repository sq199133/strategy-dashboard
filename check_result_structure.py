import json, glob, os

result_dir = r'D:\QClaw_Trading\backtest_results'
files = sorted(glob.glob(os.path.join(result_dir, 'bt_*.json')), key=os.path.getmtime)
latest = files[-1]

with open(latest) as f:
    data = json.load(f)

print(f'顶层keys: {list(data.keys())}')
for k, v in data.items():
    if isinstance(v, list):
        print(f'  {k}: list[{len(v)}条]')
        if len(v) > 0 and isinstance(v[0], dict):
            print(f'    样本字段: {list(v[0].keys())[:15]}')
    elif isinstance(v, dict):
        print(f'  {k}: dict[{list(v.keys())[:10]}]')
    else:
        print(f'  {k}: {type(v).__name__} = {str(v)[:80]}')
