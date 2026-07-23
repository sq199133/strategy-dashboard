import json
import shutil
import os

POOL_FILE = 'D:/Qclaw_Trading/data/etf_pool_V1_full.json'
BACKUP_FILE = 'D:/Qclaw_Trading/data/etf_pool_V1_full.json.bak_category_fix_20260712'

# 备份
shutil.copy2(POOL_FILE, BACKUP_FILE)
print(f'备份已保存: {BACKUP_FILE}')

with open(POOL_FILE, encoding='utf-8') as f:
    data = json.load(f)

etfs = data.get('data', data.get('etfs', []))

# 修正映射
fixes = {
    '517850': '科技/TMT/AI',  # 张江ETF：半导体/科技为主，非港股
    '561380': '制造/基建/公用',  # 电网设备ETF：电网设备，非港股
}

changed = []
for e in etfs:
    new_cat = fixes.get(e['code'])
    if new_cat and e.get('category') != new_cat:
        old_cat = e.get('category', '')
        e['category'] = new_cat
        changed.append((e['code'], e['name'], old_cat, new_cat))

print(f'\n共修正 {len(changed)} 只ETF分类：')
for code, name, old, new in changed:
    print(f'  {code} {name}: [{old}] → [{new}]')

# 保存
with open(POOL_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'\n已保存: {POOL_FILE}')
