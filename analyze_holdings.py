import json, os

HISTORY_DIR = r'D:\Qclaw_Trading\data\history_long_v2'
POOL_FILE = r'D:\Qclaw_Trading\data\etf_pool_V1_full.json'

pool = json.load(open(POOL_FILE, encoding='utf-8'))
etfs = pool.get('data', pool.get('etfs', []))
code_to_name = {e['code']: e.get('name','') for e in etfs}
code_to_cat = {e['code']: e.get('category','') for e in etfs}

holdings = ['161127','513290','512870']

for code in holdings:
    fp = os.path.join(HISTORY_DIR, f'{code}.json')
    if not os.path.exists(fp):
        print(f'{code}: file not found')
        continue
    d = json.load(open(fp, encoding='utf-8'))
    recs = d.get('records', [])
    if not recs:
        print(f'{code}: no records')
        continue
    
    last3 = recs[-3:]
    cl = [r['close'] for r in recs]
    
    # compute metrics
    mom3w = cl[-1]/cl[-4]-1 if len(cl)>=4 else None
    mom1w = cl[-1]/cl[-2]-1 if len(cl)>=2 else None
    
    # MA
    ma5 = sum(cl[-5:])/5
    ma21 = sum(cl[-21:])/21 if len(cl)>=21 else None
    dev = cl[-1]/ma21-1 if ma21 else None
    
    # vol ratio
    avg_vol10 = sum(r['vol'] for r in recs[-10:])/10
    vol_ratio = recs[-1]['vol']/avg_vol10 if avg_vol10>0 else None
    
    # atr
    atr_fast_vals = []
    atr_slow_vals = []
    for i in range(21, len(cl)):
        trs = []
        for j in range(i-20, i+1):
            h = recs[j]['high']
            lo = recs[j]['low']
            pc = cl[j-1]
            tr = max(h-lo, abs(h-pc), abs(lo-pc))
            trs.append(tr)
        atr_fast_vals.append(sum(trs[-14:])/14)
        atr_slow_vals.append(sum(trs)/21)
    atr_r = atr_fast_vals[-1]/atr_slow_vals[-1] if atr_slow_vals else None
    
    # c_pattern
    body = abs(cl[-1]-recs[-1]['open'])
    u_shadow = recs[-1]['high']-max(cl[-1],recs[-1]['open'])
    l_shadow = min(cl[-1],recs[-1]['open'])-recs[-1]['low']
    s2b = u_shadow/body if body>0 else 99
    
    # b1_pattern
    b1_ok = False
    if len(recs) >= 3:
        w1 = recs[-3]
        w2 = recs[-2]
        w3 = recs[-1]
        w1_b = w1['close'] > w1['open']
        w2_b = w2['close'] > w2['open']
        w3_b = cl[-1] > recs[-1]['open']
        w1_up = w2['low'] > w1['low'] * 0.98
        avg_vol10_val = sum(r['vol'] for r in recs[-10:])/10
        vol_ok = all(recs[j]['vol'] < avg_vol10_val * 1.5 for j in range(len(recs)-3, len(recs)))
        b1_ok = w1_b and w2_b and w3_b and w1_up and vol_ok
    
    print(f'=== {code} {code_to_name.get(code,code)} ({code_to_cat.get(code,code)}) ===')
    for r in last3:
        chg = (r['close']/r['open']-1)*100
        print(f'  W{r["w"]}({r["date"]}) O={r["open"]:.3f} C={r["close"]:.3f} H={r["high"]:.3f} L={r["low"]:.3f} Vol={r["vol"]:,.0f} ({chg:+.1f}%)')
    
    print(f'  mom3w={mom3w*100:+.1f}%  mom1w={mom1w*100:+.1f}%')
    print(f'  ma5={ma5:.4f}  ma21={ma21:.4f}  dev={dev*100:+.1f}%')
    print(f'  vol_ratio={vol_ratio:.2f}  atr_ratio={atr_r:.3f}')
    print(f'  c_pattern={body>0 and s2b>1.0 and l_shadow<body*0.5 and vol_ratio<1.5 and cl[-1]>ma5>ma21 and (cl[-1]/cl[-20]-1 if len(cl)>=20 else 0)<0.5}')
    print(f'  b1_pattern={b1_ok}')
    
    # pass check
    c1 = mom3w is not None and mom3w > 0
    c2 = cl[-1] > ma5 and ma5 > ma21
    c3 = dev is not None and dev <= 0.15
    c4 = atr_r is None or atr_r >= 0.85
    passed = c1 and c2 and c3 and c4
    print(f'  check: c1={c1} c2={c2} c3={c3} c4={c4} => passed={passed}')
    print()
