import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\QClaw_Trading\data\candidate_pool_v4.json', 'r', encoding='utf-8') as f:
    v4 = json.load(f)

# 用户指定的候选池
user_pools = {
    '布林带突破': [
        ('159902','中小100ETF华夏'),
        ('160723','嘉实原油LOF'),
        ('161128','标普信息科技LOF'),
        ('163208','全球油气能源LOF'),
        ('501018','南方原油LOF'),
        ('162719','石油LOF'),
        ('512770','战略新兴ETF华夏'),
        ('161130','纳斯达克100LOF'),
        ('159928','消费ETF汇添富'),
        ('159819','人工智能ETF易方达'),
        ('162415','美国消费LOF'),
        ('159996','家电ETF国泰'),
        ('512950','央企改革ETF华夏'),
        ('159985','豆粕ETF华夏'),
        ('159852','软件ETF嘉实'),
    ],
    '趋势突破': [
        ('160723','嘉实原油LOF'),
        ('161129','原油LOF易方达'),
        ('159902','中小100ETF华夏'),
        ('512770','战略新兴ETF华夏'),
        ('161128','标普信息科技LOF'),
        ('161130','纳斯达克100LOF'),
        ('512040','价值100ETF富国'),
        ('159928','消费ETF汇添富'),
        ('159852','软件ETF嘉实'),
        ('515580','科技100ETF华泰柏瑞'),
        ('162415','美国消费LOF'),
        ('160719','嘉实黄金LOF'),
        ('160216','国泰商品LOF'),
        ('162719','石油LOF'),
    ],
    '均线交叉': [
        ('160723','嘉实原油LOF'),
        ('560280','工程机械ETF广发'),
        ('159667','工业母机ETF国泰'),
        ('588220','科创100ETF鹏华'),
        ('563300','中证2000ETF华泰柏瑞'),
        ('159687','亚太精选ETF'),
    ]
}

# 建立 code -> v4_result 映射
v4_map = {}
for strat_name, strat_data in v4['results'].items():
    for e in strat_data['etfs']:
        key = (strat_name, e['code'])
        v4_map[key] = e

# 输出
print("策略        代码       名称                      v3年化    v4年化    差值")
print("-"*75)
for strat, codes in user_pools.items():
    print(f"\n【{strat}】{len(codes)}只")
    for code, name in codes:
        key = (strat, code)
        v4_r = v4_map.get(key)
        v4_ann = v4_r['annual_return'] if v4_r else 'N/A'
        print(f"  {code}  {name:<18}  {v4_ann}")