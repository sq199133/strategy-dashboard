import json, os

DATA_DIR = r"D:\QClaw_Trading\data\history"

# 删除错误的净值解析值（这些是之前用净值替代收盘价的错误数据）
BAD_RECORDS = {
    '159902': ['2026-05-22', '2026-05-25'],  # 错误值2.040/1.610
    '160723': [],  # 这只没有错误值
    '161128': ['2026-05-22'],  # 错误值0.520
}

print("=" * 60)
print("清理错误数据记录")
print("=" * 60)

for code, bad_dates in BAD_RECORDS.items():
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            records = data.get('records', [])
            original = len(records)
            
            # 过滤掉错误日期
            cleaned = [r for r in records if r['date'] not in bad_dates]
            
            if len(cleaned) < original:
                data['records'] = cleaned
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"✓ {code}: 删除{original - len(cleaned)}条错误记录")
                print(f"  保留{len(cleaned)}条")
            
            print(f"  最新3条:")
            for r in cleaned[-3:]:
                print(f"    {r['date']}: close={r['close']:.3f}")
            break

print("\n清理完成！")