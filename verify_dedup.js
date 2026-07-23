var dedup = require('./data/etf_pool_dedup_final.json');
var all = require('./data/etf_pool.js');
var json = require('./scripts/scan/etf_pool.json');

console.log('kept:', dedup.kept.length);
console.log('removed:', dedup.removed.length);
console.log('total:', dedup.kept.length + dedup.removed.length, '(should be 120)');
console.log('scripts/scan/etf_pool.json:', json.length, '只');
console.log('去重后合计:', dedup.kept.length, '+', dedup.removed.length, '=', dedup.kept.length+dedup.removed.length);

// 打印保留的ETF代码列表
var keptCodes = new Set(dedup.kept.map(e=>e.code));
var removedCodes = new Set(dedup.removed.map(e=>e.code));
var missing = all.filter(e=>!keptCodes.has(e.code)&&!removedCodes.has(e.code));
console.log('\n既不在kept也不在removed的ETF:', missing.length);
missing.forEach(e=>console.log('  ??', e.code, e.name, e.category));
