// 手动补充ETF名称（基于常见ETF代码）
var fs = require('fs');
var POOL_FILE = 'D:/QClaw_Trading/data/etf_pool.js';
var pool = require(POOL_FILE);

// ETF代码→名称映射（内置知识库）
var NAME_MAP = {
  // 上证系列
  '510050': '上证50ETF华夏',
  '510510': '上证50ETF易方达',
  '510300': '沪深300ETF',
  '510500': '中证500ETF南方',
  '510600': '中证500ETF华夏',
  '510720': '深证ETF',
  '510880': '红利ETF华泰柏瑞',
  '510900': '恒生中国企业ETF',
  '510060': '上证50ETF',
  
  // 深100/深证系列
  '159901': '深100ETF',
  '159902': '深100ETF',
  
  // 中证系列
  '159845': '中证1000ETF',
  '159915': '创业板ETF',
  '159920': '中证500ETF',
  '159913': '中证100ETF',
  
  // 科创系列
  '561580': '科创50ETF',
  '562660': '科创50ETF',
  '562310': '科创50ETF',
  '563020': '科创ETF',
  '588190': '科创50ETF',
  
  // 金融系列
  '512880': '证券ETF国泰',
  '512700': '银行ETF南方',
  '512800': '银行ETF',
  
  // 消费系列
  '159843': '消费ETF',
  '159996': '消费ETF',
  
  // 周期系列
  '516780': '稀土ETF',
  '515210': '钢铁ETF',
  '515460': '电池ETF',
  
  // 医药系列
  '512610': '医药ETF',
  '159858': '医药ETF',
  
  // 策略系列
  '512890': '红利低波ETF',
  '512480': '半导体ETF国联安',
  
  // 跨境QDII
  '513350': '标普500ETF',
  '513650': '纳指ETF',
  '513300': '纳斯达克ETF华夏',
  '513080': '恒生科技ETF',
  '513800': '日经ETF',
  '513500': '标普500ETF博时',
  '513400': '道琼斯ETF',
  '513730': '恒生互联网ETF',
  
  // 商品
  '518850': '黄金ETF',
  
  // 债券
  '511010': '国债ETF',
  '511260': '国债ETF',
  
  // 其他
  '159601': '创成长ETF',
  '159510': '创业板ETF',
  '159209': '医疗ETF',
  '159119': '消费ETF',
  '159298': 'MSCI中国ETF',
  '159992': '创业板ETF',
  '159995': '芯片ETF',
  '159928': '消费ETF',
  '159981': '能源ETF',
  '515980': '人工智能ETF华富'
};

// 更新名称
var updated = 0;
pool.forEach(function(e) {
  if (NAME_MAP[e.code]) {
    if (e.name === e.code || e.name === '待补充') {
      e.name = NAME_MAP[e.code];
      updated++;
      console.log('✅ ' + e.code + ' → ' + e.name);
    }
  }
});

// 保存
var jsContent = '// ETF池 v4.3 - 补充名称 (' + updated + '只)\n'
  + '// 更新日期: ' + new Date().toISOString().slice(0, 10) + '\n'
  + 'module.exports = ' + JSON.stringify(pool, null, 2) + ';\n';
fs.writeFileSync(POOL_FILE, jsContent, 'utf8');

console.log('\n=== 完成 ===');
console.log('成功补充：' + updated + '只');
console.log('池大小：' + pool.length + '只');
