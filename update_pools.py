import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\data\candidate_pool_v4.json', 'r', encoding='utf-8') as f:
    v4 = json.load(f)

# 当前候选池
user_pools = {
    '布林带突破': [
        ('159902','中小100ETF华夏'),('160723','嘉实原油LOF'),('161128','标普信息科技LOF'),
        ('163208','全球油气能源LOF'),('501018','南方原油LOF'),('162719','石油LOF'),
        ('512770','战略新兴ETF华夏'),('161130','纳斯达克100LOF'),('159928','消费ETF汇添富'),
        ('159819','人工智能ETF易方达'),('162415','美国消费LOF'),('159996','家电ETF国泰'),
        ('512950','央企改革ETF华夏'),('159985','豆粕ETF华夏'),('159852','软件ETF嘉实'),
    ],
    '趋势突破': [
        ('160723','嘉实原油LOF'),('161129','原油LOF易方达'),('159902','中小100ETF华夏'),
        ('512770','战略新兴ETF华夏'),('161128','标普信息科技LOF'),('161130','纳斯达克100LOF'),
        ('512040','价值100ETF富国'),('159928','消费ETF汇添富'),('159852','软件ETF嘉实'),
        ('515580','科技100ETF华泰柏瑞'),('162415','美国消费LOF'),('160719','嘉实黄金LOF'),
        ('160216','国泰商品LOF'),('162719','石油LOF'),
    ],
    '均线交叉': [
        ('160723','嘉实原油LOF'),('560280','工程机械ETF广发'),('159667','工业母机ETF国泰'),
        ('588220','科创100ETF鹏华'),('563300','中证2000ETF华泰柏瑞'),('159687','亚太精选ETF'),
    ]
}

# 要新增的（年化>=20%且交易>=4次的）
add_map = {
    '布林带突破': ['563230','501225','159363','159206','589600','588230','588170','588830','588910','513850'],
    '趋势突破': ['159206','561380','159363','588170','501225','563230','588850','517520','159387','588910'],
    '均线交叉': ['162719','588170','159363','159206','588850','563230','561380','161128','513850','161130','159869','161129','160216','159326']
}

# v4映射
v4_map = {}
for strat_name, strat_data in v4['results'].items():
    for e in strat_data['etfs']:
        v4_map[(strat_name, e['code'])] = e

# 构建新候选池
for strat in user_pools:
    existing = {c[0] for c in user_pools[strat]}
    add_codes = add_map[strat]
    for code in add_codes:
        if code not in existing:
            r = v4_map.get((strat, code))
            if r:
                user_pools[strat].append((code, r['name']))

# 输出
for strat, items in user_pools.items():
    print(f"{strat}: {len(items)}只")
    for code, name in items:
        r = v4_map.get((strat, code))
        ann = r['annual_return'] if r else '?'
        print(f"  {code} {name} 年化{ann}%")