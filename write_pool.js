var fs = require('fs');
var f = require('./data/etf_pool_dedup_final.json');
var kept = f.kept;

var content = [
  '// ETF池 v4.2 - 基于持仓去重 (Jaccard>=0.6) 共' + kept.length + '只',
  '// 更新日期: 2026-04-19',
  '// 保护名单: 159338(中证A500), 510300(沪深300) 无论Jaccard多高都保留',
  '// 剔除16只高度重叠ETF（见 data/etf_pool_dedup_final.json）',
  '',
  'module.exports = ' + JSON.stringify(kept, null, 2) + ';'
].join('\n');

fs.writeFileSync('D:/QClaw_Trading/data/etf_pool.js', content, 'utf8');
console.log('[OK] etf_pool.js 已更新，共 ' + kept.length + ' 只');
