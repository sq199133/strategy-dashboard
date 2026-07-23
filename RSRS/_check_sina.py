import sys, os, warnings, json
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')

STALE_ETF_SINA = {
    '510050': 'sh510050',
    '159915': 'sz159915',
    '513500': 'sh513500',
    '513100': 'sh513100',
    '515080': 'sh515080',
}

with open(r'D:\QClaw_Trading\RSRS\_sina_check_out.txt','w',encoding='utf-8') as f:
    f.write('Sina file check for stale ETFs:\n')
    f.write(f'{"Code":<8}{"SinaFile":<16}{"Exists":<8}{"SinaDate":<14}{"HistDate":<14}\n')
    
    for code, sina_file in STALE_ETF_SINA.items():
        sina_path = rf'D:\QClaw_Trading\data\daily_sina\{sina_file}.json'
        hist_path = rf'D:\QClaw_Trading\data\history\{code}.json'
        
        exists = os.path.exists(sina_path)
        sina_date = 'N/A'
        hist_date = 'N/A'
        
        if exists:
            try:
                with open(sina_path, 'r', encoding='utf-8') as fh:
                    sj = json.load(fh)
                if isinstance(sj, list) and sj:
                    sina_date = sj[-1].get('date', sj[-1].get('day', 'N/A'))
                elif isinstance(sj, dict):
                    sr = sj.get('records', sj.get('data', []))
                    if sr:
                        sina_date = sr[-1].get('date', sr[-1].get('day', 'N/A'))
            except Exception as e:
                sina_date = f'ERR'
        
        if os.path.exists(hist_path):
            try:
                with open(hist_path, 'r', encoding='utf-8') as fh:
                    j = json.load(fh)
                recs = j.get('records', [])
                if recs:
                    hist_date = recs[-1]['date']
            except:
                pass
        
        f.write(f'{code:<8}{sina_file:<16}{str(exists):<8}{sina_date:<14}{hist_date:<14}\n')
    
    f.write('\n\nCache quote files:\n')
    cache_map = {
        '510050': 'quote_sh510050.json',
        '159915': 'quote_sz159915.json',
        '513500': 'quote_sh513500.json',
        '513100': 'quote_sh513100.json',
        '515080': 'quote_sh515080.json',
    }
    for code, qfile in cache_map.items():
        cp = rf'D:\QClaw_Trading\data\cache\{qfile}'
        if os.path.exists(cp):
            try:
                with open(cp, 'r', encoding='utf-8') as fh:
                    qj = json.load(fh)
                # figure out the last date from quote file
                if isinstance(qj, list) and qj:
                    last = qj[-1]
                    qdate = last.get('date', last.get('day', 'N/A'))
                    qclose = last.get('close', last.get('price', 'N/A'))
                    f.write(f'  CACHE {qfile}: date={qdate} close={qclose}\n')
                elif isinstance(qj, dict):
                    keys = list(qj.keys())
                    f.write(f'  CACHE {qfile}: keys={keys[:5]}\n')
            except Exception as e:
                f.write(f'  CACHE {qfile}: ERR {e}\n')
        else:
            f.write(f'  CACHE {qfile}: NOT FOUND\n')
