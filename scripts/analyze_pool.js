// 分析ETF数据质量
var fs = require('fs');
var path = require('path');

var HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
var POOL_FILE = 'D:\\QClaw_Trading\\scripts\\scan\\etf_pool.json';

var pool = JSON.parse(fs.readFileSync(POOL_FILE, 'utf8'));
var poolCodes = {};
pool.forEach(function(e){ poolCodes[e.code] = e; });

var files = fs.readdirSync(HIST_DIR).filter(function(f){ return f.endsWith('.json'); });
var results = [];
files.forEach(function(f){
  var code = f.replace('.json','');
  var d = JSON.parse(fs.readFileSync(path.join(HIST_DIR, f), 'utf8'));
  var r = d.records || [];
  if (r.length < 60) return;
  var pc = code.replace('sz','').replace('sh','');
  var poolInfo = poolCodes[pc] || null;
  results.push({
    code: code,
    name: poolInfo ? poolInfo.name : '(不在池内)',
    category: poolInfo ? poolInfo.category : 'N/A',
    bars: r.length,
    oldest: r[r.length-1].date,
    newest: r[0].date
  });
});

results.sort(function(a,b){ return a.oldest.localeCompare(b.oldest); });
console.log('=== ETF数据概况 ===');
console.log('扫描池内ETF:', results.filter(function(r){ return !!r.name && r.name !== '(不在池内)'; }).length, '只');
console.log('有历史数据文件:', results.length, '只');
console.log('数据最早:', results[0].code, results[0].oldest, results[0].name);
console.log('数据最新:', results[results.length-1].code, results[results.length-1].newest);
console.log('\n=== 扫描池内ETF数据详情 ===');
var inPool = results.filter(function(r){ return !!r.name && r.name !== '(不在池内)'; });
inPool.forEach(function(r){
  console.log(r.code + ' ' + r.name + ' ' + r.bars + '条 ' + r.oldest + '~' + r.newest + (r.bars < 100 ? ' [数据较少]':''));
});
