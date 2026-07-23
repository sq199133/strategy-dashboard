import json, os

codes = ['510880', '159981', '513400', '562500', '588910', '501018', '159107', '520870']
base = r'D:\Qclaw_Trading\data\history_long_v2'

for code in codes:
    fp = os.path.join(base, f'{code}.json')
    if os.path.exists(fp):
        d = json.load(open(fp, encoding='utf-8'))
        if isinstance(d, dict):
            keys = list(d.keys())
            recs = d.get('records', [])
            print(f"{code}: dict {keys}, records={len(recs)}")
            if len(recs) > 0:
                print(f"  first: {recs[0]}")
                print(f"  last:  {recs[-1]}")
        else:
            print(f"{code}: list, len={len(d)}")
    else:
        print(f"{code}: NOT FOUND")
