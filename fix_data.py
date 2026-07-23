import json, os

DATA_DIR = r"D:\QClaw_Trading\data\history"

for code in ['160723', '161128']:
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            records = data.get('records', [])

            # 保留2026-05-21及之前的数据
            filtered = [r for r in records if r['date'] <= '2026-05-21']

            removed = len(records) - len(filtered)
            if removed > 0:
                data['records'] = filtered
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f'✓ {code} 已修复（删除{removed}条错误记录）')
            else:
                print(f'- {code} 无需修复')
            break
