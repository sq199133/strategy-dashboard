import sys, warnings, os, pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')
sys.path.insert(0, r'D:\QClaw_Trading\RSRS')

# Try to find where data files are
for root, dirs, files in os.walk(r'D:\QClaw_Trading'):
    for fn in files:
        if fn.startswith('etf_daily_') and fn.endswith('.csv'):
            fp = os.path.join(root, fn)
            try:
                dft = pd.read_csv(fp)
                last = str(dft['date'].values[-1])[:10]
                code = fn.replace('etf_daily_','').replace('.csv','')
                print(f'{fp} | rows={len(dft)} | last={last}')
            except:
                pass
