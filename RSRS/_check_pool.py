import sys, os, warnings, json
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')

POOL = {
    '510050': 'SH50',
    '510300': 'HS300',
    '510500': 'ZZ500',
    '512100': 'ZZ1000',
    '159915': 'CYB',
    '588000': 'KC50',
    '513500': 'SP500',
    '513100': 'NSDQ',
    '518880': 'GOLD',
    '162411': 'OIL',
    '515080': 'ZSHL',
}

# Sina file name mapping
SINA_MAP = {
    '510050': 'sh510050',
    '510300': 'sh510300',
    '510500': 'sh510500',
    '512100': 'sh512100',
    '159915': 'sz159915',
    '588000': 'sh588000',
    '513500': 'sh513500',
    '513100': 'sh513100',
    '518880': 'sh518880',
    '162411': 'sz162411',
    '515080': 'sh515080',
}

STALE_THRESHOLD = '2026-07-15'
TODAY = '2026-07-17'

stale = []
ok = []
missing = []

with open(r'D:\QClaw_Trading\RSRS\_pool_status_out.txt','w',encoding='utf-8') as f:
    f.write(f'{"Code":<8}{"Name":<6}{"HistDate":<14}{"HistRows":>8}{"SinaDate":<12}{"Status":<14}\n')
    f.write('='*70 + '\n')
    
    for code, name in POOL.items():
        hist_path = rf'D:\QClaw_Trading\data\history\{code}.json'
        sina_key = SINA_MAP.get(code, code)
        sina_path = rf'D:\QClaw_Trading\data\daily_sina\{sina_key}.json'
        
        hist_date = 'MISSING'
        hist_rows = 0
        sina_date = 'N/A'
        
        # Load history
        if os.path.exists(hist_path):
            try:
                with open(hist_path, 'r', encoding='utf-8') as fh:
                    j = json.load(fh)
                recs = j.get('records', [])
                if recs:
                    hist_date = recs[-1]['date']
                    hist_rows = len(recs)
            except Exception as e:
                hist_date = f'ERROR'
        
        # Load sina reference
        if os.path.exists(sina_path):
            try:
                with open(sina_path, 'r', encoding='utf-8') as fh:
                    sj = json.load(fh)
                if isinstance(sj, list) and sj:
                    sina_date = sj[-1].get('date', sj[-1].get('day', 'N/A'))
                elif isinstance(sj, dict):
                    sr = sj.get('records', sj.get('data', []))
                    if sr:
                        sina_date = sr[-1].get('date', sr[-1].get('day', 'N/A'))
            except:
                sina_date = 'ERR'
        
        # Status
        if hist_date == 'MISSING':
            status = 'MISSING'
            missing.append(code)
        elif hist_date < STALE_THRESHOLD:
            status = 'STALE'
            stale.append((code, name, hist_date, sina_date, hist_rows))
        else:
            status = 'OK'
            ok.append((code, name, hist_date, hist_rows))
        
        f.write(f'{code:<8}{name:<6}{hist_date:<14}{hist_rows:>8}  {sina_date:<12}{status:<14}\n')
    
    f.write('\n=== Summary ===\n')
    f.write(f'Total: {len(POOL)} | OK: {len(ok)} | Stale: {len(stale)} | Missing: {len(missing)}\n')
    
    if stale:
        f.write('\n--- STALE: history < ' + STALE_THRESHOLD + ' ---\n')
        f.write(f'{"Code":<8}{"Name":<6}{"HistoryDate":<14}{"SinaDate":<12}{"Rows":>8}\n')
        for code, name, hdate, sdate, rows in sorted(stale, key=lambda x: x[2]):
            f.write(f'{code:<8}{name:<6}{hdate:<14}{sdate:<12}{rows:>8}\n')
    
    if ok:
        f.write('\n--- OK: history >= ' + STALE_THRESHOLD + ' ---\n')
        for code, name, hdate, rows in sorted(ok, key=lambda x: x[2]):
            f.write(f'{code:<8}{name:<6}{hdate:<14}{rows:>8}\n')

print('Done. See _pool_status_out.txt')
