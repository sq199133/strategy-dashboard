/**
 * ETF补充分析 - 改进版
 * 对同类ETF进行严格筛选，只保留最有代表性的
 */

const fs = require('fs');
const path = require('path');

// 读取去重后的68只ETF池
const dedupPath = path.join(__dirname, '../../data/etf_pool_dedup.json');
const dedupData = JSON.parse(fs.readFileSync(dedupPath, 'utf-8'));
const existingCodes = new Set(dedupData.pool.map(e => e.code));

console.log('当前ETF池数量:', existingCodes.size);

// 待补充ETF及其详细信息
const candidateETFs = [
  // 宽基 - 需要判断是否真的缺失
  { code: '510050', name: '上证50ETF华夏', category: 'A股宽基', index: '上证50', size: 680, priority: 1 },
  { code: '510510', name: '上证50ETF易方达', category: 'A股宽基', index: '上证50', size: 120, priority: 2 },
  { code: '159915', name: '创业板ETF', category: 'A股宽基', index: '创业板指', size: 450, priority: 1 },
  { code: '159901', name: '深证100ETF', category: 'A股宽基', index: '深证100', size: 85, priority: 1 },
  { code: '588190', name: '科创100ETF', category: 'A股宽基', index: '科创100', size: 95, priority: 2 },
  { code: '563020', name: '中证2000ETF', category: 'A股宽基', index: '中证2000', size: 8, priority: 2 },
  
  // 金融地产
  { code: '512880', name: '证券ETF国泰', category: '金融地产', index: '证券公司', size: 320, priority: 1 },
  { code: '512700', name: '证券ETF南方', category: '金融地产', index: '证券公司', size: 150, priority: 2 },
  { code: '512800', name: '银行ETF华宝', category: '金融地产', index: '中证银行', size: 95, priority: 1 },
  
  // 消费医药
  { code: '159843', name: '消费ETF', category: '消费医药', index: '中证消费', size: 75, priority: 1 },
  { code: '159996', name: '消费ETF易方达', category: '消费医药', index: '中证消费', size: 45, priority: 2 },
  { code: '159119', name: '消费ETF', category: '消费医药', index: '消费80', size: 25, priority: 3 },
  { code: '159928', name: '消费ETF', category: '消费医药', index: '中证消费', size: 35, priority: 2 },
  { code: '159858', name: '医疗ETF', category: '消费医药', index: '中证医疗', size: 55, priority: 1 },
  { code: '159992', name: '创新药ETF', category: '消费医药', index: '创新药', size: 48, priority: 1 },
  { code: '512610', name: '恒生医疗ETF', category: '跨境QDII', index: '恒生医疗', size: 42, priority: 1 },
  
  // 周期资源
  { code: '515210', name: '钢铁ETF', category: '周期资源', index: '中证钢铁', size: 18, priority: 1 },
  
  // 策略指数
  { code: '510880', name: '红利ETF', category: '策略指数', index: '上证红利', size: 185, priority: 1 },
  { code: '512890', name: '红利低波ETF', category: '策略指数', index: '红利低波', size: 78, priority: 1 },
  { code: '561580', name: '红利ETF', category: '策略指数', index: '中证红利', size: 35, priority: 2 },
  { code: '159298', name: '红利ETF', category: '策略指数', index: '中证红利', size: 28, priority: 2 },
  { code: '510720', name: '央企ETF', category: '策略指数', index: '央企改革', size: 52, priority: 1 },
  { code: '510060', name: '央企ETF', category: '策略指数', index: '央企改革', size: 48, priority: 2 },
  
  // 科技
  { code: '159913', name: '科技ETF', category: '科技', index: '中证科技', size: 65, priority: 1 },
  
  // 新能源
  { code: '515460', name: '电池ETF', category: '新能源', index: '电池指数', size: 38, priority: 2 },
  
  // 债券（新类别）
  { code: '511010', name: '国债ETF', category: '债券', index: '国债', size: 280, priority: 1 },
  { code: '511260', name: '十年国债ETF', category: '债券', index: '国债', size: 185, priority: 2 },
];

console.log('候选补充ETF数量:', candidateETFs.length);

// 检查哪些是真正缺失的类别
const missingCategories = {
  '上证50': true,
  '证券公司': true,
  '中证银行': true,
  '中证消费': true,
  '创新药': true,
  '中证钢铁': true,
  '上证红利': true,
  '红利低波': true,
  '央企改革': true,
  '深证100': true,
  '中证科技': true,
  '债券': true
};

// 检查现有池中是否已覆盖这些指数
console.log('\n检查现有池中的指数覆盖情况：');
const existingIndices = new Map();
dedupData.pool.forEach(etf => {
  // 根据ETF代码推断跟踪指数
  const indexMap = {
    '510500': '中证500',
    '588000': '科创50',
    '512050': '中证A500',
    '512100': '中证1000',
    '588220': '科创100',
    '159591': '中证A50',
    '159602': '中国A50',
    '159531': '中证2000',
    '159350': '深证50',
    '510300': '沪深300',
    '520500': '创业板',
    '588200': '科创芯片',
    '515880': '通信',
    '515070': '人工智能',
    '512660': '军工',
    '159206': '卫星',
    '159326': '电网设备',
    '515790': '光伏',
    '159566': '储能电池',
    '516160': '新能源',
    '561910': '电池',
    '515700': '新能源车',
    '512010': '医药',
    '512170': '医疗',
    '512290': '生物医药',
    '560080': '中药',
    '512690': '消费',
    '159667': '食品饮料',
    '159253': '银行',
    '159260': '证券',
    '512200': '房地产',
    '516650': '有色金属',
    '516150': '稀土',
    '562800': '稀有金属',
    '515900': '央企创新',
    '159259': '成长',
    '588020': '科创成长',
    '159525': '红利低波',
    '159117': '标普红利',
    '159332': '央企红利',
    '513660': '恒生指数',
    '513180': '恒生科技',
    '513050': '中概互联',
    '513330': '恒生互联网',
    '513720': '港股互联网',
    '513060': '恒生医疗',
    '513120': '港股创新药',
    '513500': '标普500',
    '513100': '纳指100',
    '513520': '日经225',
    '513030': '德国DAX',
    '513400': '道琼斯',
    '513850': '美国50',
    '159329': '沙特',
    '159100': '巴西',
    '008763': '中国A50',
    '539003': '德国',
    '518880': '黄金',
    '159562': '黄金股',
    '159985': '豆粕',
    '520580': '能源化工'
  };
  
  const index = indexMap[etf.code];
  if (index) {
    existingIndices.set(index, etf.code);
  }
});

console.log('已覆盖指数:', existingIndices.size);

// 最终补充清单（严格筛选）
const finalAdditions = [];

// 1. 上证50 - 现有池中没有
if (!existingIndices.has('上证50')) {
  finalAdditions.push({ code: '510050', reason: '补充上证50，大盘蓝筹核心指数' });
}

// 2. 证券公司 - 现有池中159260是全指证券，补充更主流的证券公司
if (!existingIndices.has('证券公司')) {
  finalAdditions.push({ code: '512880', reason: '补充证券ETF，券商板块核心标的' });
}

// 3. 银行 - 现有池中159253是中证银行，已覆盖
// 但512800是银行ETF华宝，规模更大，可以考虑替换或补充
// 跳过，已有覆盖

// 4. 中证消费 - 现有池中512690是消费ETF，但可能不是中证消费指数
// 159843是中证消费ETF，补充更标准的消费指数
finalAdditions.push({ code: '159843', reason: '补充中证消费ETF，消费板块核心标的' });

// 5. 创新药 - 现有池中没有
if (!existingIndices.has('创新药')) {
  finalAdditions.push({ code: '159992', reason: '补充创新药ETF，医药细分赛道' });
}

// 6. 恒生医疗 - 现有池中有513060恒生医疗ETF，已覆盖
// 512610也是恒生医疗ETF，跳过
// 跳过，已有覆盖

// 7. 钢铁 - 现有池中没有
if (!existingIndices.has('钢铁')) {
  finalAdditions.push({ code: '515210', reason: '补充钢铁ETF，周期资源板块' });
}

// 8. 红利相关 - 现有池中有159525红利低波、159117标普红利、159332央企红利
// 但缺少上证红利（510880）这个经典红利指数
finalAdditions.push({ code: '510880', reason: '补充上证红利ETF，经典红利策略' });

// 9. 央企改革 - 现有池中有515900央企创新，但央企改革是不同的指数
finalAdditions.push({ code: '510720', reason: '补充央企改革ETF，央企主题' });

// 10. 深证100 - 现有池中没有
if (!existingIndices.has('深证100')) {
  finalAdditions.push({ code: '159901', reason: '补充深证100ETF，深市核心宽基' });
}

// 11. 中证科技 - 现有池中没有单独的中证科技ETF
finalAdditions.push({ code: '159913', reason: '补充中证科技ETF，科技板块宽基' });

// 12. 创业板指 - 现有池中520500是创业板ETF，但需要确认是否是创业板指
// 159915是创业板ETF易方达，规模更大，可以考虑补充或替换
// 现有池中已有创业板ETF，跳过

// 13. 科创100 - 现有池中588220是科创100ETF鹏华，已覆盖
// 跳过，已有覆盖

// 14. 中证2000 - 现有池中159531是中证2000，已覆盖
// 跳过，已有覆盖

// 15. 债券 - 现有池中没有债券ETF，这是全新的资产类别！
finalAdditions.push({ code: '511010', reason: '补充国债ETF，债券资产类别（全新）' });
finalAdditions.push({ code: '511260', reason: '补充十年国债ETF，债券资产类别（全新）' });

// 输出结果
console.log('\n' + '='.repeat(60));
console.log('最终补充清单');
console.log('='.repeat(60));

console.log('\n【建议补充】', finalAdditions.length, '只');
finalAdditions.forEach((item, i) => {
  const etf = candidateETFs.find(e => e.code === item.code);
  if (etf) {
    console.log(`${i+1}. ${item.code} ${etf.name} (${etf.category}, 规模${etf.size}亿)`);
    console.log(`   理由: ${item.reason}`);
  }
});

console.log('\n【纯代码清单】');
console.log(finalAdditions.map(item => item.code).join('\n'));

// 保存结果
const output = {
  additions: finalAdditions,
  total: finalAdditions.length,
  timestamp: new Date().toISOString()
};

const outputPath = path.join(__dirname, '../../data/etf_final_additions.json');
fs.writeFileSync(outputPath, JSON.stringify(output, null, 2), 'utf-8');
console.log(`\n结果已保存到: ${outputPath}`);

console.log('\n【补充后ETF池规模】');
console.log(`  原68只 + 新增${finalAdditions.length}只 = ${68 + finalAdditions.length}只`);
