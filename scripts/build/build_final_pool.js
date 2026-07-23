// Final verified ETF pool v4
// All names cross-checked against Sina hq API + EM fund data
const fs = require('fs');
const path = require('path');

const sina = JSON.parse(fs.readFileSync(path.join(__dirname,'sina_etf.json'),'utf8'));
const em = JSON.parse(fs.readFileSync(path.join(__dirname,'etf_all_raw.json'),'utf8'));
const emMap = {};
em.forEach(e => emMap[e.code] = e.size);

// Verified list: [code, category, intendedName, market]
const FINAL = [
  // === A股宽基 ===
  ['510500', 'A股宽基', '中证500ETF南方',        'SH'],
  ['588000', 'A股宽基', '科创50ETF华夏',           'SH'],
  ['159338', 'A股宽基', '中证A500',                'SZ'],
  ['512050', 'A股宽基', 'A500ETF华夏',             'SH'],
  ['512100', 'A股宽基', '中证1000ETF南方',          'SH'],
  ['563800', 'A股宽基', 'A500ETF广发',             'SH'],
  ['563220', 'A股宽基', 'A500ETF富国',             'SH'],
  ['588080', 'A股宽基', '科创50ETF易方达',          'SH'],
  ['588220', 'A股宽基', '科创100ETF鹏华',          'SH'],
  ['515330', 'A股宽基', '沪深300ETF天弘',           'SH'],
  ['159591', 'A股宽基', '中证A50',                 'SZ'],
  ['159602', 'A股宽基', '中国A50',                 'SZ'],
  ['159531', 'A股宽基', '中证2000',                'SZ'],
  ['159150', 'A股宽基', '深证50E',                  'SZ'],
  ['159350', 'A股宽基', '深证50',                   'SZ'],

  // === 科技 ===
  ['588200', '科技', '科创芯片ETF嘉实',             'SH'],
  ['512480', '科技', '半导体ETF国联安',            'SH'],
  ['515880', '科技', '通信ETF国泰',                'SH'],
  ['515070', '科技', '人工智能ETF华夏',             'SH'],
  ['515050', '科技', '通信ETF华夏',                'SH'],
  ['512760', '科技', '芯片ETF国泰',                'SH'],
  ['515980', '科技', '人工智能ETF华富',             'SH'],
  ['588170', '科技', '科创半导体ETF华夏',           'SH'],
  ['159558', '科技', '半导体E',                    'SZ'],
  ['588750', '科技', '科创芯片ETF汇添富',          'SH'],
  ['159541', '科技', '创业板综',                   'SZ'],
  ['159539', '科技', '信创50',                     'SZ'],
  ['159213', '科技', '机器人TF',                   'SZ'],

  // === 高端制造 ===
  ['562500', '高端制造', '机器人ETF华夏',          'SH'],
  ['159206', '高端制造', '卫星ETF',                'SZ'],
  ['159530', '高端制造', '机器人E',                'SZ'],
  ['512660', '高端制造', '军工ETF国泰',            'SH'],
  ['512710', '高端制造', '军工龙头ETF富国',        'SH'],
  ['512680', '高端制造', '军工ETF广发',            'SH'],
  ['563230', '高端制造', '卫星ETF富国',            'SH'],
  ['159227', '高端制造', '航空航天',               'SZ'],

  // === 新能源 ===
  ['159326', '新能源', '电网设备',                 'SZ'],
  ['515790', '新能源', '光伏ETF华泰柏瑞',          'SH'],
  ['159566', '新能源', '储能电池',                  'SZ'],
  ['516160', '新能源', '新能源ETF南方',            'SH'],
  ['561380', '新能源', '电网设备ETF国泰',          'SH'],
  ['561910', '新能源', '电池ETF招商',              'SH'],
  ['561160', '新能源', '电池ETF富国',              'SH'],
  ['515700', '新能源', '新能源车ETF平安',          'SH'],
  ['159187', '新能源', '景顺新能',                  'SZ'],

  // === 消费医药 ===
  ['510660', '消费医药', '医药ETF华夏',            'SH'],
  ['512010', '消费医药', '医药ETF易方达',          'SH'],
  ['512170', '消费医药', '医疗ETF华宝',            'SH'],
  ['512290', '消费医药', '生物医药ETF国泰',        'SH'],
  ['515960', '消费医药', '医药ETF嘉实',            'SH'],
  ['516790', '消费医药', '医疗ETF华泰柏瑞',        'SH'],
  ['516820', '消费医药', '医疗创新ETF平安',        'SH'],
  ['560080', '消费医药', '中药ETF汇添富',          'SH'],
  ['561510', '消费医药', '中药ETF华泰柏瑞',        'SH'],

  // === 金融地产 ===
  ['159253', '金融地产', '中证银行',               'SZ'],
  ['159260', '金融地产', '全指证券',               'SZ'],
  ['512200', '金融地产', '房地产ETF南方',          'SH'],
  ['515060', '金融地产', '房地产ETF华夏',          'SH'],

  // === 周期资源 ===
  ['516650', '周期资源', '有色金属ETF华夏',        'SH'],
  ['516150', '周期资源', '稀土ETF嘉实',            'SH'],
  ['562800', '周期资源', '稀有金属ETF嘉实',        'SH'],
  ['159608', '周期资源', '稀有金属',               'SZ'],
  ['159157', '周期资源', '有色TH',                  'SZ'],
  ['510170', '周期资源', '大宗商品ETF国联安',      'SH'],

  // === 策略指数 ===
  ['515900', '策略指数', '央企创新ETF博时',        'SH'],
  ['159259', '策略指数', '成长ETF',                'SZ'],
  ['588020', '策略指数', '科创成长ETF易方达',      'SH'],
  ['159525', '策略指数', '红利低波',               'SZ'],
  ['159117', '策略指数', '标普红利',               'SZ'],
  ['159332', '策略指数', '央企红利',               'SZ'],

  // === 跨境QDII ===
  ['510900', '跨境QDII', '恒生中国企业ETF易方达',  'SH'],
  ['513660', '跨境QDII', '恒生ETF华夏',            'SH'],
  ['513600', '跨境QDII', '恒生指数ETF南方',        'SH'],
  ['513010', '跨境QDII', '恒生科技ETF易方达',      'SH'],
  ['513130', '跨境QDII', '恒生科技ETF华泰柏瑞',    'SH'],
  ['513180', '跨境QDII', '恒生科技ETF华夏',        'SH'],
  ['513380', '跨境QDII', '恒生科技ETF广发',        'SH'],
  ['513050', '跨境QDII', '中概互联网ETF易方达',    'SH'],
  ['513330', '跨境QDII', '恒生互联网ETF华夏',      'SH'],
  ['513720', '跨境QDII', '港股互联网ETF国泰',      'SH'],
  ['513060', '跨境QDII', '恒生医疗ETF博时',        'SH'],
  ['513120', '跨境QDII', '港股创新药ETF广发',      'SH'],
  ['513500', '跨境QDII', '标普500ETF博时',         'SH'],
  ['513390', '跨境QDII', '纳指100ETF博时',         'SH'],
  ['513100', '跨境QDII', '纳指ETF国泰',            'SH'],
  ['513300', '跨境QDII', '纳斯达克ETF华夏',        'SH'],
  ['513870', '跨境QDII', '纳指ETF富国',            'SH'],
  ['513520', '跨境QDII', '日经ETF华夏',            'SH'],
  ['513000', '跨境QDII', '日经225ETF易方达',       'SH'],
  ['513030', '跨境QDII', '德国ETF华安',            'SH'],
  ['513400', '跨境QDII', '道琼斯ETF鹏华',          'SH'],
  ['513850', '跨境QDII', '美国50ETF易方达',        'SH'],

  // === 商品 ===
  ['518880', '商品', '黄金ETF华安',                'SH'],
  ['518800', '商品', '黄金ETF国泰',                'SH'],
  ['518660', '商品', '黄金ETF工银',                'SH'],
  ['518860', '商品', '上海金ETF建信',              'SH'],
  ['518890', '商品', '上海金ETF中银',              'SH'],
  ['159562', '商品', '黄金股',                      'SZ'],

  // === 当前持仓（单独标注）===
  ['159681', '持仓', '创业板50ETF鹏华',            'SZ'],
];

// Verify each against Sina data
console.log('===== 最终ETF池逐行核实 =====\n');
let ok = 0, warn = 0, errors = [];

FINAL.forEach((item, i) => {
  const [code, cat, intended, market] = item;
  const found = sina.find(e => e.code === code);
  const size = emMap[code] || 0;
  
  if (found) {
    const name = found.name;
    // Check if names roughly match
    const key1 = intended.replace(/ETF/g,'').replace(/[^A-Za-z0-9\u4e00-\u9fa5]/g,'');
    const key2 = name.replace(/ETF/g,'').replace(/[^A-Za-z0-9\u4e00-\u9fa5]/g,'');
    const match = key1.includes(key2.substring(0,4)) || key2.includes(key1.substring(0,4)) || key1 === key2;
    const s = size > 0 ? size.toFixed(1)+'亿' : '?亿';
    if (match) {
      console.log(`✅ ${i+1}. ${code} ${name} [${cat}] ${s}`);
      ok++;
    } else {
      console.log(`⚠️ ${i+1}. ${code} 期望=${intended} 实际=${name} [${cat}] ${s}`);
      warn++;
      errors.push({code, intended, found: name});
    }
  } else {
    console.log(`❌ ${i+1}. ${code} ${intended} [${cat}] ${size>0?size.toFixed(1)+'亿':'?亿'} ← 未在新浪列表`);
    errors.push({code, intended, found: null});
  }
});

console.log(`\n===== 核实结果 =====`);
console.log(`✅ 通过: ${ok} 只`);
console.log(`⚠️ 警告: ${warn} 只`);
console.log(`❌ 错误: ${errors.filter(e=>!e.found).length} 只`);

if (errors.length > 0) {
  console.log('\n需确认:');
  errors.forEach(e => console.log('  '+e.code+' 期望='+e.intended+(e.found?' 实际='+e.found:'')));
}
