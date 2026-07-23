# -*- coding: gbk -*-
data = open(r'D:\QClaw_Trading\scripts\backtest\_bt_out.txt','rb').read()
text = data.decode('gbk','ignore')
lines = [l.strip() for l in text.split('\n') if l.strip()]

# Filter out progress bars
filtered = []
skip_patterns = ['Pp%', '═══', '━━━━']
for l in lines:
    # Skip if mostly progress bars
    stripped = l.replace(' ','')
    pct_count = stripped.count('%') + stripped.count('P')
    if pct_count >= 10: continue
    if any(p in l for p in skip_patterns): filtered.append(l); continue
    if l.startswith('P'): continue
    # Keep meaningful lines
    filtered.append(l)

print('\n'.join(filtered))
