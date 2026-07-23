// 合并新ETF并去重
var fs = require('fs');
var path = require('path');

var POOL_FILE = 'D:/QClaw_Trading/data/etf_pool.js';

// 现有池
var existing = require(POOL_FILE);
var existingCodes = new Set(existing.map(function(e) { return e.code; }));
console.log('现有池：' + existing.length + '只');

// 新增标的（合并两个列表去重）
var newCodes = [
  // 分类列表
  '510050', '510510', '159845', '159915', // 宽基
  '512880', '512700', // 金融
  '159843', '159996', // 消费
  '516780', '515210', '513350', // 周期
  '512610', '159858', // 医药
  '510880', '512890', '561580', // 策略
  '513650', '513300', '513080', '513800', '520830', // 跨境
  // 扁平列表
  '159901', '159601', '159510', '562660', '588190', '563020',
  '159209', '515460', '159119', '510720', '159913', '562310',
  '513500', '159920', '513400', '513730', '159298', '159992',
  '159995', '159928', '512800', '510060', '511010', '511260',
  '159981', '518850'
];

// 去重
newCodes = [...new Set(newCodes)];
console.log('新增标的（去重后）：' + newCodes.length + '只');

// 过滤已存在的
var trulyNew = newCodes.filter(function(c) { return !existingCodes.has(c); });
console.log('真正新增：' + trulyNew.length + '只');
console.log('已存在跳过：' + (newCodes.length - trulyNew.length) + '只');
console.log('已存在：' + newCodes.filter(function(c) { return existingCodes.has(c); }).join(', '));

// 分类映射（根据代码前缀判断）
function getCategory(code) {
  if (code.startsWith('51') && parseInt(code) >= 513000 && parseInt(code) < 514000) return '跨境QDII';
  if (code.startsWith('51') && parseInt(code) >= 511000 && parseInt(code) < 512000) return '债券';
  if (code.startsWith('518') || code.startsWith('520')) return '商品';
  if (code.startsWith('588') || code.startsWith('56') && parseInt(code) >= 560000) return '科创';
  if (code.startsWith('510')) return 'A股宽基';
  if (code.startsWith('512')) return '行业主题';
  if (code.startsWith('515') || code.startsWith('516')) return '行业主题';
  if (code.startsWith('159')) return '深市ETF';
  return '其他';
}

function getMarket(code) {
  if (code.startsWith('5') || code.startsWith('0')) return 'SH';
  if (code.startsWith('1')) return 'SZ';
  return 'SH';
}

// 构建新ETF对象
var newEtfs = trulyNew.map(function(code) {
  return {
    code: code,
    name: '待补充',
    market: getMarket(code),
    category: getCategory(code),
    size: 0
  };
});

console.log('\n待补充名称的标的：');
newEtfs.forEach(function(e) {
  console.log('  ' + e.code + ' (' + e.market + ', ' + e.category + ')');
});

// 合并
var merged = existing.concat(newEtfs);
console.log('\n合并后总数：' + merged.length + '只');

// 保存
var jsContent = '// ETF池 v4.3 - 新增' + trulyNew.length + '只待补充名称\n'
  + '// 更新日期: ' + new Date().toISOString().slice(0, 10) + '\n'
  + 'module.exports = ' + JSON.stringify(merged, null, 2) + ';\n';

fs.writeFileSync(POOL_FILE, jsContent, 'utf8');
console.log('已保存：' + POOL_FILE);

// 输出去重报告
console.log('\n=== 去重报告 ===');
console.log('原有：' + existing.length + '只');
console.log('新增：' + trulyNew.length + '只');
console.log('合并：' + merged.length + '只');
console.log('\n下一步：需要为' + trulyNew.length + '只新ETF补充名称');
