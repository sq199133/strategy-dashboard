import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

def load_recs(code):
    for prefix in ['', 'sh', 'sz']:
        fname = f'data/history_long_v2/{code}.json'
        if not os.path.exists(fname):
            fname = f'data/history_long_v2/{prefix}{code}.json'
        if os.path.exists(fname):
            with open(fname, encoding='utf-8') as f:
                d = json.load(f)
            return d.get('records', d) if isinstance(d, dict) else d
    return []

# Check 161127 and others from Live scan
codes = ['161127', '161126', '517850', '159687']
for code in codes:
    recs = load_recs(code)
    if not recs:
        print(f'{code}: 无数据')
        continue
    closes = [r['close'] for r in recs]
    weeks = [r.get('w', r.get('week', '')) for r in recs]
    i = len(recs) - 1
    
    mom1w = closes[i]/closes[i-1]-1
    mom3w = closes[i]/closes[i-3]-1
    mom8w = closes[i]/closes[i-8]-1
    score = 0.4*mom1w + 0.4*mom3w + 0.2*mom8w
    ma5 = sum(closes[i-4:i+1])/5
    ma21 = sum(closes[i-20:i+1])/21
    dev = closes[i]/ma21 - 1
    ma_ok = ma5 > ma21
    dev_ok = dev <= 0.15
    score_ok = score > 0
    
    # ATR
    trs = []
    for j in range(i-20, i+1):
        trs.append(abs(closes[j]-closes[j-1]))
    atr14 = sum(trs[-14:])/14
    atr21 = sum(trs)/21
    atr_r = atr14/atr21 if atr21 > 0 else 1
    atr_ok = atr_r >= 0.85
    
    print(f'{code}: score={score*100:.2f}% mom1w={mom1w*100:+.2f}% mom3w={mom3w*100:+.2f}% '
          f'dev={dev*100:+.2f}% atr={atr_r:.2f}')
    print(f'  本周{weeks[i]} close={closes[i]:.4f} 上周{weeks[i-1]} close={closes[i-1]:.4f} '
          f'3周前{weeks[i-3]} close={closes[i-3]:.4f}')
    print(f'  MA5/21: {ma_ok} {ma5:.4f}/{ma21:.4f}  dev_ok={dev_ok} score_ok={score_ok} atr_ok={atr_ok}')
    print(f'  PASSED = {score_ok and ma_ok and dev_ok and atr_ok}')
    print()
