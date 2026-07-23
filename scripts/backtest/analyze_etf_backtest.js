var fs = require('fs');
var r = JSON.parse(fs.readFileSync('D:/QClaw_Trading/scripts/backtest/backtest_result_2026-04-17.json', 'utf8'));
var results = r.all_results;

console.log('=== 104只ETF本地回测 (2026-04-17) ===');
console.log('共同起点: ' + r.common_start + ' → ' + r.common_end + '  (' + r.years.toFixed(1) + '年)');
console.log('结果数量: ' + results.length + ' 只');

// 按score排序（跑赢基准程度）
var sorted = results.slice().sort(function(a,b){ return b.score - a.score; });

console.log('\n--- 跑赢持有TOP10 (' + sorted.filter(function(x){ return x.score > 0; }).length + '只) ---');
sorted.filter(function(x){ return x.score > 0; }).slice(0,10).forEach(function(x){
  var ann = (x.annual * 100).toFixed(1) + '%';
  var bm  = (x.bm_annual * 100).toFixed(1) + '%';
  var diff= (x.diff_bm * 100).toFixed(1) + '%';
  var wr  = (x.win_rate * 100).toFixed(0) + '%';
  console.log(x.etf_name + ' ' + x.code + ': 年化' + ann + ' vs 基准' + bm + ' 超额' + diff + ' 胜率' + wr + ' 交易' + x.n_trades + '次');
});

console.log('\n--- 最差10只 ---');
sorted.slice(-10).forEach(function(x){
  var ann = (x.annual * 100).toFixed(1) + '%';
  var diff= (x.diff_bm * 100).toFixed(1) + '%';
  console.log(x.etf_name + ' ' + x.code + ': 年化' + ann + ' 超额' + diff);
});

// 汇总
var byWin = { win: 0, lose: 0 };
sorted.forEach(function(x){ if (x.score > 0) byWin.win++; else byWin.lose++; });
console.log('\n--- 汇总 ---');
console.log('跑赢持有: ' + byWin.win + ' 只 (' + (byWin.win / sorted.length * 100).toFixed(1) + '%)');
console.log('跑输持有: ' + byWin.lose + ' 只 (' + (byWin.lose / sorted.length * 100).toFixed(1) + '%)');
var avgAnnual = results.reduce(function(a,b){ return a + b.annual; }, 0) / results.length;
var avgBm    = results.reduce(function(a,b){ return a + b.bm_annual; }, 0) / results.length;
console.log('平均年化收益: ' + (avgAnnual * 100).toFixed(1) + '%');
console.log('平均基准年化: ' + (avgBm * 100).toFixed(1) + '%');
var avgWinRate = results.reduce(function(a,b){ return a + b.win_rate; }, 0) / results.length;
console.log('平均单次胜率: ' + (avgWinRate * 100).toFixed(1) + '%');
