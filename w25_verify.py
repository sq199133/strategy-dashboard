import sys, json
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Check daily data for 161127
# Use the local JSON file as source (has daily data embedded)
with open(r'D:\Qclaw_Trading\data\history_long_v2\161127.json', encoding='utf-8') as f:
    d = json.load(f)
recs = d.get('records', [])

print(f'Total weekly records: {len(recs)}')
print(f'Last 10 weeks:')
for r in recs[-10:]:
    print(f'  {r["w"]} ({r["date"]}): close={r["close"]}')

# The local file only has weekly data, not daily
# But the scan uses live API which may have more recent weekly data
# Let me check what dates the API would return for W25

# June 19, 2026 = Dragon Boat Festival (holiday in China)
# June 18 = Wednesday, June 17 = Tuesday
# The last trading day before the holiday is June 17 (Wednesday)
# Week 25 in ISO: June 15 (Mon) - June 21 (Sun)
# But in Chinese trading context, "week" is Mon-Fri
# June 15 (Mon) = day 1 of W25, June 19 (Fri/holiday) = day 5 of W25

# Let's verify using datetime isocalendar
test_dates = ['2026-06-15', '2026-06-16', '2026-06-17', '2026-06-18', '2026-06-19', '2026-06-20', '2026-06-21', '2026-06-22']
for ds in test_dates:
    dt = datetime.strptime(ds, '%Y-%m-%d')
    y, w, dow = dt.isocalendar()
    print(f'  {ds} (weekday={dt.weekday()}, Fri of this week): ISO {y}-W{w:02d} weekday={dow}')

print()
print('=== MOM1W DISCREPANCY ANALYSIS ===')
print()
print('SCAN result for 161127:')
print('  mom1w = 8.97%, mom3w = 14.76%, score = 12.0%')
print('  Implied: W25 close = 2.029 / 1.0897 = 1.862 (API)')
print('  Local file: W24 close = 1.763, W26 close = 2.029')
print('  Local mom1w = 2.029/1.763-1 = +15.1%')
print()
print('  LOCAL FILE MISSING: W25 (June 15-21, or June 22-28 in M-F convention)')
print('  The API weekly aggregation includes W25, local does not.')
print()
print('=== RECALCULATED LOCAL SCORE (without W25) ===')
# Using local file data, pretending mom1w uses W24
mom1w_local = 2.029 / 1.763 - 1  # uses W24 as "last week"
mom3w_local = 2.029 / 1.812 - 1  # uses W23
mom8w_local = 2.029 / 1.830 - 1  # uses W18 (8 weeks back)
score_local = 0.4 * mom1w_local + 0.4 * mom3w_local + 0.2 * mom8w_local
print(f'  mom1w (local, W24→W26) = {mom1w_local*100:+.2f}%')
print(f'  mom3w (local, W23→W26) = {mom3w_local*100:+.2f}%')
print(f'  mom8w (local, W18→W26) = {mom8w_local*100:+.2f}%')
print(f'  score = {score_local*100:.2f}%  (vs scan: 12.00%)')
print()
print('The SCAN uses LIVE API data which has W25; local file misses W25.')
