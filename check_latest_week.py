import json, os
from datetime import datetime

# Check latest date in data files
d = r'D:\Qclaw_Trading\data\history_long_v2'
files = [f for f in os.listdir(d) if f.endswith('.json')]

latest_dates = []
for fname in files[:50]:
    f = json.load(open(os.path.join(d, fname)))
    recs = f.get('records', f) if isinstance(f, dict) else f
    if recs:
        r = recs[-1]
        ds = r.get('date', r[0]) if isinstance(r, dict) else r[0]
        latest_dates.append(ds)

latest_dates.sort(reverse=True)
print(f'Top 10 latest dates in data (sample 50 files):')
for d in latest_dates[:10]:
    try:
        dt = datetime.strptime(d, '%Y-%m-%d')
        y, w, _ = dt.isocalendar()
        print(f'  {d} → {y}-W{w:02d}')
    except:
        print(f'  {d}')

# Also check what today is
from datetime import timezone, timedelta
tz = timezone(timedelta(hours=8))
now = datetime.now(tz)
y, w, d = now.isocalendar()
print(f'\nToday: {now.strftime("%Y-%m-%d %H:%M")} → ISO {y}-W{w:02d} Day {d}')
