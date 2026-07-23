// 持仓对比分析：当前持仓 vs 扫描结果
var fs = require('fs');

// 当前持仓
var holdings = [
  { code: '159681', name: '创业板50ETF鹏华', buyPrice: 1.717, status: '持有' },
  { code: '512770', name: '战略新兴ETF华夏', buyPrice: 2.395, status: '周一卖出' },
  { code: '512220', name: 'TMTETF景顺', buyPrice: 3.235, status: '持有' },
  { code: '516390', name: '新能源汽车ETF', buyPrice: 1.094, status: '持有' },
  { code: '513100', name: '纳指ETF国泰', buyPrice: 1.902, status: '持有' }
];

// 扫描结果（从扫描输出提取）
var scanResults = {
  '159681': { signal: '不在新池中', star: '-', pct20: '-' },
  '512770': { signal: '不在新池中', star: '-', pct20: '-' },
  '512220': { signal: '不在新池中', star: '-', pct20: '-' },
  '516390': { signal: '不在新池中', star: '-', pct20: '-' },
  '513100': { signal: 'BUY', star: '⭐⭐', pct20: '7.3%', note: '但被相关性过滤排除(corr=0.77)' }
};

// BUY候选
var buyCandidates = [
  { code: '159259', name: '成长ETF', star: '⭐⭐⭐⭐', pct20: 17.6, maxCorr: '-' },
  { code: '515700', name: '新能源车ETF平安', star: '⭐⭐⭐', pct20: 12.3, maxCorr: 0.66 },
  { code: '159602', name: '中国A50', star: '⭐⭐', pct20: 7.1, maxCorr: 0.68 },
  { code: '511010', name: '国债ETF', star: '⭐⭐', pct20: 0.3, maxCorr: '-' }
];

// 被相关性过滤的强力BUY
var filteredBuys = [
  { code: '515880', name: '通信ETF国泰', star: '⭐⭐⭐', pct20: 25.1, corr: 0.88 },
  { code: '159298', name: 'MSCI中国ETF', star: '⭐⭐⭐', pct20: 12.5, corr: 0.84 },
  { code: '515000', name: '科技ETF', star: '⭐⭐⭐', pct20: 11.3, corr: 0.92 },
  { code: '515070', name: '人工智能ETF华夏', star: '⭐⭐⭐', pct20: 11.8, corr: 0.88 },
  { code: '159901', name: '深100ETF', star: '⭐⭐⭐', pct20: 8.0, corr: 0.83 },
  { code: '159350', name: '深证50', star: '⭐⭐⭐', pct20: 7.6, corr: 0.78 }
];

console.log('=== 持仓对比分析 ===\n');

console.log('【当前持仓在新池中的状态】\n');
holdings.forEach(function(h) {
  var s = scanResults[h.code];
  if (s.signal === '不在新池中') {
    console.log('⚠️ ' + h.code + ' ' + h.name + ' → 不在新ETF池(60只)中！');
    console.log('   该标的在去重时被剔除（跟踪的指数有更优替代）');
  } else {
    console.log(h.code + ' ' + h.name + ' → 信号:' + s.signal + ' 星级:' + s.star);
  }
});

console.log('\n【扫描TOP BUY候选】\n');
buyCandidates.forEach(function(c, i) {
  console.log((i+1) + '. ' + c.code + ' ' + c.name + ' ' + c.star + ' 20日涨幅:' + c.pct20 + '% maxCorr:' + c.maxCorr);
});

console.log('\n【被相关性过滤的强力BUY（corr>0.70）】\n');
filteredBuys.forEach(function(c) {
  console.log('  ' + c.code + ' ' + c.name + ' ' + c.star + ' 20日:' + c.pct20 + '% 相关:' + c.corr);
});

console.log('\n=== 问题分析 ===\n');
console.log('1. 当前5只持仓中有4只不在新ETF池中（去重时被剔除）');
console.log('2. 唯一在新池中的513100（纳指ETF），扫描结果也是BUY但被相关性过滤');
console.log('3. 原计划买入510500（中证500），扫描结果仅⭐⭐ HOLD');
console.log('4. 515880通信ETF国泰 20日涨幅25.1%是全市场最强，但被相关性过滤');
console.log('5. 成长ETF 159259 四星领涨 17.6%，通过相关性过滤');

console.log('\n=== 调仓建议 ===\n');
console.log('方案A：保守调整（仅执行已定计划）');
console.log('  卖出 512770 战略新兴 → 买入 159259 成长ETF（四星，17.6%）');
console.log('  保留其他4只不动');
console.log('');
console.log('方案B：全面重建（用新池最优标的替换）');
console.log('  卖出 512770 → 买入 159259 成长ETF ⭐⭐⭐⭐');
console.log('  卖出 512220 TMT → 买入 515700 新能源车 ⭐⭐⭐ (TMT在新池已剔除)');
console.log('  卖出 516390 新能源车 → 买入 159602 中国A50 ⭐⭐ (516390也不在新池)');
console.log('  保留 159681 创业板50（虽然不在新池，但持仓盈利中）');
console.log('  保留 513100 纳指ETF（虽然被相关性过滤，但作为跨境分散有价值）');
console.log('');
console.log('方案C：激进重建（5只全换为扫描最优组合）');
console.log('  159259 成长ETF ⭐⭐⭐⭐ 17.6%');
console.log('  515700 新能源车 ⭐⭐⭐ 12.3% maxCorr=0.66');
console.log('  159602 中国A50 ⭐⭐ 7.1% maxCorr=0.68');
console.log('  511010 国债ETF ⭐⭐ 0.3% (防御性配置)');
console.log('  + 1只从FILTERED中选（需放宽相关性阈值）');
