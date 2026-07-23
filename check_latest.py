import sys, os, json, glob
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')

files = glob.glob('data/history_long_v2/*.json')
print(f'Total files: {len(files)}')

# Check a few files for latest date
samples = files[::40][:5]
for f in samples:
    fname = f.split('\\')[-1]
    try:
        with open(f, encoding='utf-8') as fh:
            d = json.load(fh)
        if isinstance(d, dict):
            recs = d.get('records', [])
        else:
            recs = d
        if recs:
            last = recs[-1]
            date = last.get('date_end', last.get('date', '?'))
            print(f'{fname}: last date = {date}, total weeks = {len(recs)}')
    except Exception as e:
        print(f'{fname}: ERROR {e}')
