import json

# 检查池中ETF数据格式
codes = ['510300','518880','159928','512100','510050','159902','159949','512800','512400','512200','510160','159905','510810']
for code in codes:
    fp = f'D:\\QClaw_Trading\\data\\history\\{code}.json'
    try:
        raw = json.load(open(fp, encoding='utf-8'))
        t = type(raw).__name__
        if isinstance(raw, dict):
            keys = list(raw.keys())
            n = len(raw.get('records', []))
            print(f'{code}: dict  keys={keys}  n_records={n}')
        elif isinstance(raw, list):
            n = len(raw)
            sample = {}
            if n > 0 and isinstance(raw[0], dict):
                sample = {k: type(raw[0][k]).__name__ for k in list(raw[0].keys())[:6]}
            print(f'{code}: list  n={n}  sample={sample}')
    except Exception as e:
        print(f'{code}: ERROR {e}')
