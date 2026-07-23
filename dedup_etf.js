// dedup_etf.js v3
// 基于持仓相似度(Jaccard>=0.6)和原始规模，对ETF池进行合理去重
// 特殊规则：SPECIAL_KEEP 名单内的ETF不受去重影响，无论规模大小
const fs   = require('fs');
const path = require('path');

const rawHoldings     = require('./data/etf_holdings_raw.json');
const similarityPairs = require('./data/etf_similarity_pairs.json');
const ALL_ETFS        = require('./data/etf_pool.js');

// ── 核心变量 ───────────────────────────────
var removed        = new Set();
var kept           = {};
var protectedCodes = new Set();

// ── 手动保护名单（无论Jaccard多高都保留）───
var SPECIAL_KEEP = new Set([
  '159338',  // 中证A500（跟踪中证A500指数，与沪深300编制逻辑不同）
  '510300',  // 沪深300ETF（跟踪沪深300指数，与中证A500编制逻辑不同）
]);
console.log('🛡️  保护名单: ' + [...SPECIAL_KEEP].join(', '));

// 预保留保护名单（直接加入kept，跳过去重）
SPECIAL_KEEP.forEach(function(code){
  var e = ALL_ETFS.find(x=>x.code===code);
  if (e) {
    kept[code] = e;
    protectedCodes.add(code);
    console.log('   🛡️ 预保留: ' + code + ' ' + e.name);
  } else {
    console.log('   ⚠️ 保护名单中找不到: ' + code);
  }
});

// ── 持仓数据 ───────────────────────────────
var etfsWithHoldings = Object.values(rawHoldings).filter(e => e.holdings.length > 0);

// ── 相似度查找表 ───────────────────────────
var simMap = {};
similarityPairs.forEach(function(p){ simMap[p.pair] = p.jaccard; });
function getSim(c1, c2) {
  var key = c1 < c2 ? c1 + '|' + c2 : c2 + '|' + c1;
  return simMap[key] || 0;
}

// ── 贪心去重（Jaccard >= 0.6）──────────────
var THRESHOLD = 0.6;

// 按持仓数量降序，先处理数据最丰富的
var sorted = etfsWithHoldings.slice().sort(function(a,b){
  return b.holdings.length - a.holdings.length;
});

sorted.forEach(function(etf) {
  if (removed.has(etf.code)) return;
  if (kept[etf.code]) return;
  if (protectedCodes.has(etf.code)) return;    // 保护名单，跳过去重

  // 找所有与etf高度相似的ETF
  var group = [etf.code];
  etfsWithHoldings.forEach(function(other) {
    if (other.code === etf.code) return;
    if (removed.has(other.code) || kept[other.code]) return;
    if (protectedCodes.has(other.code)) return;  // 保护名单不归入任何组
    if (getSim(etf.code, other.code) >= THRESHOLD) {
      group.push(other.code);
    }
  });

  if (group.length === 1) {
    // 无高度相似 → 保留
    kept[etf.code] = etf;
  } else {
    // 有相似ETF → 全部加入removed，再选best复活
    group.forEach(function(code){ removed.add(code); });

    // 选best：规模大的优先，size=0时用持仓数量
    var best = etfsWithHoldings.find(function(e){ return e.code === etf.code; });
    group.forEach(function(code){
      var candidate = etfsWithHoldings.find(function(e){ return e.code === code; });
      if (!candidate) return;
      var sa = (ALL_ETFS.find(function(x){ return x.code===best.code; })||{}).size||0;
      var sb = (ALL_ETFS.find(function(x){ return x.code===candidate.code; })||{}).size||0;
      if (sb > sa || (sb===sa && candidate.holdings.length > best.holdings.length)) {
        best = candidate;
      }
    });

    removed.delete(best.code);   // 复活best
    kept[best.code] = best;     // 保留

    // 打印分组
    console.log('━━━ 同组(' + group.length + '只) J>=' + THRESHOLD + ' ━━━');
    group.sort(function(a,b){
      var sa = (ALL_ETFS.find(function(x){ return x.code===a; })||{}).size||0;
      var sb = (ALL_ETFS.find(function(x){ return x.code===b; })||{}).size||0;
      return sb - sa;
    });
    group.forEach(function(code){
      var e = etfsWithHoldings.find(function(x){ return x.code===code; });
      var isBest = code === best.code;
      console.log('  ' + (isBest?'✅':'❌') + ' ' + code + ' ' + (e?e.name:'(?)') +
        '  size:' + ((ALL_ETFS.find(function(x){return x.code===code;})||{}).size||0) + '亿' +
        (isBest?' [MAX]':'  J='+getSim(code,best.code).toFixed(3)));
    });
    // 共同持仓
    if (best.holdings.length > 0) {
      var bestSet = new Set(best.holdings.map(function(h){ return h.stockCode; }));
      var common = [];
      group.forEach(function(code){
        if (code===best.code) return;
        var o = etfsWithHoldings.find(function(x){ return x.code===code; });
        if (!o) return;
        o.holdings.forEach(function(h){
          if (bestSet.has(h.stockCode) && !common.find(function(c){ return c.stockCode===h.stockCode; })) {
            common.push(h);
          }
        });
      });
      if (common.length > 0) {
        console.log('  共同: ' + common.map(function(c){ return c.stockName+'('+c.stockCode+')'; }).join(', '));
      }
    }
  }
});

// ── 纳入无持仓ETF（QDII/黄金/豆粕等）───
var keptCodes = new Set(Object.keys(kept));
var removedCodes = new Set(removed);
ALL_ETFS.forEach(function(e){
  if (!keptCodes.has(e.code) && !removedCodes.has(e.code)) {
    kept[e.code] = e;   // 无持仓，全部保留
  }
});

// ── 汇总统计 ──────────────────────────────────
var finalList   = Object.values(kept);
var finalCodes  = new Set(Object.keys(kept));
var removedList = ALL_ETFS.filter(function(e){ return !finalCodes.has(e.code); });

console.log('\n' + '='.repeat(60));
console.log('去重完成！');
console.log('  原始: ' + ALL_ETFS.length + ' 只');
console.log('  保留: ' + finalList.length + ' 只');
console.log('  剔除: ' + removedList.length + ' 只');

var cats = {};
finalList.forEach(function(e){
  if (!cats[e.category]) cats[e.category] = 0;
  cats[e.category]++;
});
console.log('\n保留ETF行业分布:');
Object.keys(cats).sort().forEach(function(c){
  console.log('  ' + c + ': ' + cats[c] + '只');
});

console.log('\n剔除的ETF:');
removedList.forEach(function(e){
  console.log('  ❌ ' + e.code + ' ' + e.name + ' [' + e.category + ']');
});

// ── 保存两份 ──────────────────────────────────
var finalEtfs = finalList.map(function(e){
  return {
    code:     e.code,
    name:     e.name,
    market:   e.market,
    category: e.category,
    size:     e.size || 0
  };
});

fs.writeFileSync(
  path.join(__dirname, 'scripts', 'scan', 'etf_pool.json'),
  JSON.stringify(finalEtfs, null, 2), 'utf8'
);
fs.writeFileSync(
  path.join(__dirname, 'data', 'etf_pool_dedup_final.json'),
  JSON.stringify({kept:finalEtfs, removed:removedList}, null, 2), 'utf8'
);
console.log('\n[OK] scripts/scan/etf_pool.json      (新ETF池)');
console.log('[OK] data/etf_pool_dedup_final.json  (完整报告)');
console.log('\n下一步：将保留名单写入 etf_pool.js 运行全量扫描');
