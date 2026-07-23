/**
 * 分析建议补充的ETF列表
 * 目的：剔除已有同类的，只补充真正未覆盖的
 */

const fs = require('fs');
const path = require('path');

// 读取去重后的68只ETF池
const dedupPath = path.join(__dirname, '../../data/etf_pool_dedup.json');
const dedupData = JSON.parse(fs.readFileSync(dedupPath, 'utf-8'));
const existingCodes = new Set(dedupData.pool.map(e => e.code));

console.log('当前ETF池数量:', existingCodes.size);

// 建议补充的ETF列表（去重）
const suggestedETFs = [
  // 第一部分（分类明确的）
  '510050', '510510', '159845', '159915', // 宽基
  '512880', '512700', // 金融
  '159843', '159996', // 消费
  '516780', '515210', '513350', // 周期
  '512610', '159858', // 医药
  '510880', '512890', '561580', // 策略
  '513650', '513300', '513080', '513800', '520830', // 跨境
  
  // 第二部分（未分类的）
  '159901', '159601', '159510', '562660', '588190', '563020',
  '159209', '515460', '159119', '510720', '159913', '562310',
  '159920', '510900', '513400', '513730', '159298', '159992',
  '512480', '159995', '159928', '515980', '512800',
  '510060', '511010', '511260', '159981', '518850'
];

// 去重
const uniqueSuggested = [...new Set(suggestedETFs)];
console.log('建议补充ETF数量（去重后）:', uniqueSuggested.length);

// 分类：已在池中 vs 新增
const inPool = [];
const notInPool = [];

uniqueSuggested.forEach(code => {
  if (existingCodes.has(code)) {
    inPool.push(code);
  } else {
    notInPool.push(code);
  }
});

console.log('\n已在池中:', inPool.length, '只');
console.log(inPool.join(', '));

console.log('\n不在池中:', notInPool.length, '只');
console.log(notInPool.join(', '));

// ETF信息查询（基于常见ETF知识）
const etfInfo = {
  // 宽基
  '510050': { name: '上证50ETF华夏', category: 'A股宽基', index: '上证50' },
  '510510': { name: '上证50ETF易方达', category: 'A股宽基', index: '上证50' },
  '159845': { name: '中证1000ETF', category: 'A股宽基', index: '中证1000' },
  '159915': { name: '创业板ETF', category: 'A股宽基', index: '创业板指' },
  '159901': { name: '深证100ETF', category: 'A股宽基', index: '深证100' },
  '159601': { name: '中证1000ETF', category: 'A股宽基', index: '中证1000' },
  '159510': { name: '中证500ETF', category: 'A股宽基', index: '中证500' },
  '562660': { name: '中证1000ETF', category: 'A股宽基', index: '中证1000' },
  '588190': { name: '科创100ETF', category: 'A股宽基', index: '科创100' },
  
  // 金融
  '512880': { name: '证券ETF国泰', category: '金融地产', index: '证券公司' },
  '512700': { name: '证券ETF南方', category: '金融地产', index: '证券公司' },
  '512800': { name: '银行ETF华宝', category: '金融地产', index: '中证银行' },
  
  // 消费
  '159843': { name: '消费ETF', category: '消费医药', index: '中证消费' },
  '159996': { name: '消费ETF易方达', category: '消费医药', index: '中证消费' },
  
  // 周期
  '516780': { name: '稀土ETF华安', category: '周期资源', index: '稀土' },
  '515210': { name: '钢铁ETF', category: '周期资源', index: '中证钢铁' },
  '513350': { name: '标普500ETF', category: '跨境QDII', index: '标普500' },
  
  // 医药
  '512610': { name: '恒生医疗ETF', category: '跨境QDII', index: '恒生医疗' },
  '159858': { name: '医疗ETF', category: '消费医药', index: '中证医疗' },
  
  // 策略
  '510880': { name: '红利ETF', category: '策略指数', index: '上证红利' },
  '512890': { name: '红利低波ETF', category: '策略指数', index: '红利低波' },
  '561580': { name: '红利ETF', category: '策略指数', index: '中证红利' },
  
  // 跨境
  '513650': { name: '纳指ETF', category: '跨境QDII', index: '纳指100' },
  '513300': { name: '纳斯达克ETF', category: '跨境QDII', index: '纳指100' },
  '513080': { name: '恒生科技ETF', category: '跨境QDII', index: '恒生科技' },
  '513800': { name: '日经ETF', category: '跨境QDII', index: '日经225' },
  '520830': { name: '豆粕ETF', category: '商品', index: '豆粕' },
  '513730': { name: '恒生科技ETF', category: '跨境QDII', index: '恒生科技' },
  
  // 其他
  '563020': { name: '中证2000ETF', category: 'A股宽基', index: '中证2000' },
  '159209': { name: '有色金属ETF', category: '周期资源', index: '有色金属' },
  '515460': { name: '电池ETF', category: '新能源', index: '电池指数' },
  '159119': { name: '消费ETF', category: '消费医药', index: '消费80' },
  '510720': { name: '央企ETF', category: '策略指数', index: '央企改革' },
  '159913': { name: '科技ETF', category: '科技', index: '中证科技' },
  '562310': { name: '中证1000ETF', category: 'A股宽基', index: '中证1000' },
  '159920': { name: '沪深300ETF', category: 'A股宽基', index: '沪深300' },
  '510900': { name: '恒生ETF', category: '跨境QDII', index: '恒生指数' },
  '159298': { name: '红利ETF', category: '策略指数', index: '中证红利' },
  '159992': { name: '创新药ETF', category: '消费医药', index: '创新药' },
  '512480': { name: '半导体ETF', category: '科技', index: '半导体' },
  '159995': { name: '芯片ETF', category: '科技', index: '芯片产业' },
  '159928': { name: '消费ETF', category: '消费医药', index: '中证消费' },
  '515980': { name: '人工智能ETF', category: '科技', index: '人工智能' },
  '510060': { name: '央企ETF', category: '策略指数', index: '央企改革' },
  '511010': { name: '国债ETF', category: '债券', index: '国债' },
  '511260': { name: '十年国债ETF', category: '债券', index: '国债' },
  '159981': { name: '能源化工ETF', category: '商品', index: '能源化工' },
  '518850': { name: '黄金ETF', category: '商品', index: '黄金' }
};

// 分析需要补充的ETF
console.log('\n' + '='.repeat(60));
console.log('补充分析');
console.log('='.repeat(60));

const toAdd = [];
const toSkip = [];
const skipReasons = {};

notInPool.forEach(code => {
  const info = etfInfo[code];
  if (!info) {
    console.log(`⚠️ ${code}: 无ETF信息，跳过`);
    toSkip.push(code);
    skipReasons[code] = '无ETF信息';
    return;
  }
  
  // 检查是否与已有ETF重叠
  let overlap = false;
  let overlapCode = null;
  
  // 检查同类别、同指数的ETF
  dedupData.pool.forEach(existing => {
    if (existing.category === info.category) {
      // 特殊情况处理
      if (info.index === '上证50' && existing.code === '510050') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '中证1000' && existing.code === '512100') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '创业板指' && existing.code === '159915') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '沪深300' && existing.code === '510300') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '中证500' && existing.code === '510500') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '证券公司' && existing.code === '512880') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '中证银行' && existing.code === '512800') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '纳指100' && existing.code === '513100') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '恒生科技' && existing.code === '513180') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '恒生指数' && existing.code === '513660') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '日经225' && existing.code === '513520') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '标普500' && existing.code === '513500') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '半导体' && existing.code === '588200') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '芯片产业' && existing.code === '588200') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '人工智能' && existing.code === '515070') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '黄金' && existing.code === '518880') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '豆粕' && existing.code === '159985') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '能源化工' && existing.code === '520580') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '稀土' && existing.code === '516150') {
        overlap = true;
        overlapCode = existing.code;
      }
      if (info.index === '有色金属' && existing.code === '516650') {
        overlap = true;
        overlapCode = existing.code;
      }
    }
  });
  
  if (overlap) {
    toSkip.push(code);
    skipReasons[code] = `与${overlapCode}重叠`;
  } else {
    toAdd.push(code);
  }
});

console.log('\n【建议补充】', toAdd.length, '只');
toAdd.forEach(code => {
  const info = etfInfo[code];
  if (info) {
    console.log(`  ${code} ${info.name} (${info.category}, ${info.index})`);
  } else {
    console.log(`  ${code} (待查证)`);
  }
});

console.log('\n【建议跳过】', toSkip.length, '只');
toSkip.forEach(code => {
  const info = etfInfo[code];
  if (info) {
    console.log(`  ${code} ${info.name} - ${skipReasons[code]}`);
  } else {
    console.log(`  ${code} - ${skipReasons[code]}`);
  }
});

// 输出最终补充清单
console.log('\n' + '='.repeat(60));
console.log('最终补充清单（纯代码）');
console.log('='.repeat(60));
console.log(toAdd.join('\n'));

// 保存结果
const output = {
  added: toAdd,
  skipped: toSkip,
  skipReasons: skipReasons,
  etfInfo: etfInfo
};

const outputPath = path.join(__dirname, '../../data/etf_new_additions.json');
fs.writeFileSync(outputPath, JSON.stringify(output, null, 2), 'utf-8');
console.log(`\n结果已保存到: ${outputPath}`);
