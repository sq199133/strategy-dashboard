import json
d = json.load(open('D:/Qclaw_Trading/scan_results/weekly_scan_v4_20260712_091406.json', encoding='utf-8'))
qual = sorted([r for r in d['all'] if r.get('passed')], key=lambda x: x.get('_adj_score', x.get('score', 0)), reverse=True)
for i, r in enumerate(qual[:10]):
    score = r.get('_adj_score', r.get('score', 0))
    print(f"{i+1} {r['code']} {r['name']} {r['cat']} close={round(r['close'],3)} score={round(score*100,1)}% mom={round(r['mom']*100,1)}% dev={round(r['dev']*100,1)}% atr={round(r.get('atr_ratio',1)*100,0)}%")
print(f"TARGET: {d['target'][0]['code']} {d['target'][0]['name']}")
print(f"SELL: {[r['code'] for r in d['sell']]}")
print(f"BUY: {[r['code'] for r in d['buy']]}")
print(f"KEEP: {[r['code'] for r in d['keep']]}")
# Current holding detail
t = d['target'][0]
print(f"\n--- HOLDING DETAIL ---")
print(f"Code: {t['code']}, Name: {t['name']}")
print(f"Category: {t['cat']}")
print(f"Close: {t['close']}, MA5: {round(t['ma5'],3)}, MA21: {round(t['ma21'],3)}")
print(f"Momentum(3w): {round(t['mom']*100,2)}%")
print(f"Deviation from MA21: {round(t['dev']*100,1)}%")
print(f"ATR ratio: {round(t.get('atr_ratio',1)*100,0)}%")
print(f"Vol ratio: {round(t.get('vol_ratio',0),2)}")
print(f"仙人指路C: {t.get('c_pattern')}")
print(f"红三兵B1: {t.get('b1_pattern')}")
