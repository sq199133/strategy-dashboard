import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

def load_recs(code):
    for prefix in ['', 'sh', 'sz']:
        fname = f'data/history_long_v2/{code}.json'
        if os.path.exists(fname):
            with open(fname, encoding='utf-8') as f:
                d = json.load(f)
            return d.get('records', d) if isinstance(d, dict) else d
        fname = f'data/history_long_v2/{prefix}{code}.json'
        if os.path.exists(fname):
            with open(fname, encoding='utf-8') as f:
                d = json.load(f)
            return d.get('records', d) if isinstance(d, dict) else d
    return []

# TOP 3 candidates detailed
tops = [
    ('515580', '科技100ETF华泰柏瑞'),
    ('512870', '杭州湾区ETF南华'),
    ('588910', '科创价值ETF建信'),
]

print('TOP 3 评分计算明细（本地数据）:')
print()
for code, name in tops:
    recs = load_recs(code)
    closes = [r['close'] for r in recs]
    weeks = [r.get('w', r.get('week', '')) for r in recs]
    dates = [r.get('date_end', r.get('date', '')) for r in recs]
    i = len(recs) - 1
    
    # Last 3 weeks prices
    print(f'{code} {name}:')
    print(f'  W26({dates[i]}) close={closes[i]:.4f}')
    print(f'  W25({dates[i-1]}) close={closes[i-1]:.4f}')
    print(f'  W23({dates[i-3]}) close={closes[i-3]:.4f}')
    print(f'  W18({dates[i-8]}) close={closes[i-8]:.4f}')
    
    mom1w = closes[i]/closes[i-1]-1
    mom3w = closes[i]/closes[i-3]-1
    mom8w = closes[i]/closes[i-8]-1
    score = 0.4*mom1w + 0.4*mom3w + 0.2*mom8w
    
    print(f'  mom1w = {closes[i]:.4f}/{closes[i-1]:.4f}-1 = {mom1w*100:+.2f}%')
    print(f'  mom3w = {closes[i]:.4f}/{closes[i-3]:.4f}-1 = {mom3w*100:+.2f}%')
    print(f'  mom8w = {closes[i]:.4f}/{closes[i-8]:.4f}-1 = {mom8w*100:+.2f}%')
    print(f'  score = 0.4*{mom1w*100:.2f}% + 0.4*{mom3w*100:.2f}% + 0.2*{mom8w*100:.2f}% = {score*100:.2f}%')
    print()

# Checks for key ETFs
print('=' * 60)
print('持仓决策校验:')
print()

prev = [
    ('517850', '张江ETF', '卖'),
    ('588910', '科创价值ETF', '留'),
    ('159572', '创业板200ETF', '卖'),
]
for code, name, action in prev:
    recs = load_recs(code)
    closes = [r['close'] for r in recs]
    weeks = [r.get('w', r.get('week', '')) for r in recs]
    i = len(recs) - 1
    mom3w = closes[i]/closes[i-3]-1
    dev = closes[i]/(sum(closes[i-20:i+1])/21)-1 if i >= 20 else 0
    print(f'  {code} {name} ({action}): mom3w={mom3w*100:+.1f}% dev={dev*100:+.1f}%')

# 161127: why it failed
print()
print('Live scan 争议ETF:')
for code in ['161127']:
    recs = load_recs(code)
    closes = [r['close'] for r in recs]
    weeks = [r.get('w', r.get('week', '')) for r in recs]
    dates = [r.get('date_end', r.get('date', '')) for r in recs]
    i = len(recs) - 1
    
    print(f'  {code} 标普生物科技LOF:')
    print(f'    本地W25缺失 → mom1w误用W24({dates[i-1]})close={closes[i-1]:.4f}')
    print(f'    score={0.4*(closes[i]/closes[i-1]-1)+0.4*(closes[i]/closes[i-3]-1)+0.2*(closes[i]/closes[i-8]-1):+.2f}%')
    ma21 = sum(closes[i-20:i+1])/21
    dev_local = closes[i]/ma21-1
    print(f'    dev={dev_local*100:.2f}% {"≤15% PASS" if dev_local <= 0.15 else ">15% FAIL"}')
