import json, urllib.request, time, datetime, sys, os

sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'D:\QClaw_Trading')

POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
OUT_DIR = r'D:\QClaw_Trading\data\daily'

# Load pool
with open(POOL_FILE, 'r', encoding='utf-8') as f:
    pool = json.load(f)
etfs = pool['data']
print(f'Loaded {len(etfs)} ETFs from V1 full pool')

# Ensure output dir
os.makedirs(OUT_DIR, exist_ok=True)

# Build market codes
def to_market_code(code):
    code = str(code)
    if code.startswith('159') or code.startswith('161'):
        return 'sz' + code
    else:
        return 'sh' + code

# Fetch from Tencent
def fetch_tencent(codes):
    codes_str = ','.join(codes)
    url = f'https://qt.gtimg.cn/q={codes_str}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('gbk', errors='replace')
    except Exception as e:
        print(f'Fetch error: {e}')
        return ''

# Parse response
def parse_tencent_resp(text):
    results = {}
    for line in text.strip().split('\n'):
        if '=' not in line:
            continue
        try:
            parts = line.split('="')[1].rstrip('";\n')
            fields = parts.split('~')
            if len(fields) < 10:
                continue
            code_raw = line.split('="')[0].strip().lstrip('v_')
            code = code_raw[2:]  # strip sz/sh prefix
            results[code] = {
                'name': fields[1],
                'price': fields[3],
                'yesterday_close': fields[4],
                'open': fields[5],
                'volume': fields[6],
                'outer_vol': fields[7],
                'bid1': fields[9],
                'ask1': fields[19],
                'date': fields[30],
                'time': fields[31],
            }
        except Exception:
            continue
    return results

# Batch fetch (50 at a time)
all_data = []
total = len(etfs)
print(f'Fetching {total} ETFs...')

for i in range(0, total, 50):
    batch = etfs[i:i+50]
    codes = [to_market_code(etf['code']) for etf in batch]
    text = fetch_tencent(codes)
    parsed = parse_tencent_resp(text)
    
    for etf in batch:
        code = str(etf['code'])
        p = parsed.get(code, {})
        if p:
            row = {
                'code': code,
                'name': etf.get('name', p.get('name', '')),
                'category': etf.get('category', ''),
                'price': p.get('price', ''),
                'yesterday_close': p.get('yesterday_close', ''),
                'change': float(p['price']) - float(p['yesterday_close']) if p.get('price') and p.get('yesterday_close') and p['yesterday_close'] != '0' else None,
                'change_pct': (float(p['price']) - float(p['yesterday_close'])) / float(p['yesterday_close']) * 100 if p.get('price') and p.get('yesterday_close') and p['yesterday_close'] != '0' else None,
                'date': p.get('date', ''),
                'time': p.get('time', ''),
            }
        else:
            row = {'code': code, 'name': etf.get('name', ''), 'category': etf.get('category', ''), 'price': '', 'yesterday_close': '', 'change': None, 'change_pct': None, 'date': '', 'time': ''}
        all_data.append(row)
    
    print(f'  Batch {i//50+1}: fetched {len(parsed)}/{len(batch)}')
    time.sleep(0.5)

# Save with timestamp
now = datetime.datetime.now()
ts = now.strftime('%Y-%m-%d_%H%M%S')
out_file = os.path.join(OUT_DIR, f'etf_daily_{ts}.json')
result = {
    'fetch_time': now.strftime('%Y-%m-%d %H:%M:%S'),
    'total': len(all_data),
    'fetched': sum(1 for x in all_data if x['price']),
    'source': 'etf_pool_V1_full.json (195 ETFs)',
    'data': all_data
}
with open(out_file, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# Also update the latest symlink
latest_file = os.path.join(OUT_DIR, 'etf_daily_latest.json')
with open(latest_file, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f'Done! Saved to {out_file}')
print(f'Fetched: {result["fetched"]}/{total}')
print(f'Latest: {latest_file}')