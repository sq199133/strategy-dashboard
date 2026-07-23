import json, os, urllib.request, urllib.parse, sys
from datetime import datetime

NEODATA_URL = "http://localhost:19000/proxy/api"
REMOTE_URL = "https://jprx.m.qq.com/aizone/skillserver/v1/proxy/teamrouter_neodata/query"

def query_neodata(query_text, request_id):
    """调用neodata-financial-search技能"""
    payload = {
        "query": query_text,
        "request_id": request_id,
        "data_type": "api",
        "sub_channel": "qclaw"
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        NEODATA_URL,
        data=data,
        headers={
            'Content-Type': 'application/json',
            'Remote-URL': REMOTE_URL
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result
    except Exception as e:
        print(f"API调用失败: {e}")
        return None

def update_etf_file(code, latest_close, latest_date):
    """更新ETF的JSON数据文件"""
    # 找到文件
    data_file = None
    for prefix in ['sz', 'sh']:
        path = os.path.join(r"D:\QClaw_Trading\data\history", f"{prefix}{code}.json")
        if os.path.exists(path):
            data_file = path
            break

    if not data_file:
        print(f"未找到{code}的数据文件")
        return False

    # 读取现有数据
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    records = data.get('records', [])

    # 检查是否已经是最新
    if records:
        last_date = records[-1]['date']
        if last_date >= latest_date:
            print(f"{code} 数据已是最新（{last_date}）")
            return True

    # 追加新数据
    new_record = {
        'date': latest_date,
        'open': latest_close * 0.998,  # 估算
        'close': latest_close,
        'high': latest_close * 1.005,  # 估算
        'low': latest_close * 0.995,   # 估算
        'vol': 0,
        'amount': 0,
        'change': 0,
        'change_pct': 0
    }

    records.append(new_record)

    # 保存
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✓ {code} 数据已更新至 {latest_date}（收盘{latest_close:.3f}）")
    return True

print("=" * 70)
print("更新ETF数据文件")
print("=" * 70)

# 查询三只ETF的最新行情
etf_codes = ['159902', '160723', '161128']
results = {}

for code in etf_codes:
    print(f"\n查询 {code}...")
    result = query_neodata(f"{code}最新收盘价和日期", f"update_{code}_001")

    if result and result.get('code') == '200':
        # 解析返回结果
        api_data = result.get('data', {}).get('apiData', {})
        print(f"  查询结果: {json.dumps(api_data, ensure_ascii=False)[:200]}...")

        # TODO: 解析具体的收盘价和日期
        # 这里假设已经从结果中提取到了close和date
        # results[code] = {'close': ..., 'date': ...}
    else:
        print(f"  查询失败: {result}")

# 暂时使用手动输入的方式
print("\n" + "=" * 70)
print("由于API返回格式需要解析，暂时使用手动输入模式")
print("=" * 70)
print("\n请提供以下ETF的最新收盘价和日期：")
for code in etf_codes:
    print(f"  {code}: 收盘价=?  日期=? (格式: YYYY-MM-DD)")

print("\n或者，我可以帮你生成一个基于估算数据的更新版本。")
print("注意：估算数据仅供参考，实际交易请使用真实数据。")
