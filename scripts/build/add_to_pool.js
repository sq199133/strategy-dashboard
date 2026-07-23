/**
 * 将4只ETF加入标的池v4
 * 2026-04-17 核实后追加
 * 
 * 核实结果：
 *  159329 SZ 沙特ETF         → 归类：跨境QDII（沙特股市）✅新增
 *  159100 SZ 巴西            → 归类：跨境QDII（巴西股市）✅新增
 *  159980 SZ 有色ETF         → 归类：周期资源 → 已存在（516650有色金属ETF华夏）→ 合并为同一标的
 *  159985 SZ 豆粕ETF         → 归类：商品（农产品期货）✅新增
 */
const POOL_V4 = require('./etf_pool_v4.js');

// 新增4只（去除重复的159980）
const NEW_ETFS = [
  { code:'159329', name:'沙特ETF',       market:'SZ', category:'跨境QDII', size:  0 },
  { code:'159100', name:'巴西',           market:'SZ', category:'跨境QDII', size:  0 },
  { code:'159985', name:'豆粕ETF',       market:'SZ', category:'商品',    size:  0 },
];

const EXISTING = new Set(POOL_V4.map(e=>e.code));
let added = 0, skipped = 0;

NEW_ETFS.forEach(e => {
  if (EXISTING.has(e.code)) {
    console.log('跳过(已存在): ' + e.code + ' ' + e.name);
    skipped++;
  } else {
    POOL_V4.push(e);
    console.log('加入: ' + e.code + ' ' + e.name + ' [' + e.category + ']');
    added++;
  }
});

// 159980去重说明：周期资源已有516650(有色金属ETF华夏,140.9亿)
// 159980(有色ETF)与516650跟踪同一指数（细分不同），保留516650
console.log('\n159980说明: 周期资源已有516650(有色金属ETF华夏,140.9亿)，159980不再重复加入');
console.log('\n加入: ' + added + ' 只 | 跳过: ' + skipped + ' 只');
console.log('新池总计: ' + POOL_V4.length + ' 只');

module.exports = POOL_V4;
