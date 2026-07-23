var fs = require('fs');
var raw = JSON.parse(fs.readFileSync('D:/QClaw_Trading/scripts/backtest/backtest_20y_trades.json', 'utf8'));
var sells = raw.filter(function(t){ return t.act === 'sell'; });
var gains = sells.map(function(s){ return s.ret; });

var wins = gains.filter(function(r){ return r > 0; });
var losses = gains.filter(function(r){ return r <= 0; });

console.log('=== 沪深300 MA20+MACD 20年回测 ===');
console.log('总交易对: ' + sells.length);
console.log('盈利: ' + wins.length + '  亏损: ' + losses.length);
console.log('胜率: ' + (wins.length / sells.length * 100).toFixed(1) + '%');
if (wins.length > 0) console.log('平均盈利: ' + (wins.reduce(function(a,b){ return a+b; },0) * 100 / wins.length).toFixed(2) + '%');
if (losses.length > 0) console.log('平均亏损: ' + (losses.reduce(function(a,b){ return a+b; },0) * 100 / losses.length).toFixed(2) + '%');
if (wins.length > 0 && losses.length > 0) {
  var avgWin = wins.reduce(function(a,b){ return a+b; },0) / wins.length;
  var avgLoss = losses.reduce(function(a,b){ return a+b; },0) / losses.length;
  console.log('盈亏比: ' + Math.abs(avgWin / avgLoss).toFixed(2));
}
console.log('最大单次盈利: ' + (Math.max.apply(null, gains) * 100).toFixed(2) + '%');
console.log('最大单次亏损: ' + (Math.min.apply(null, gains) * 100).toFixed(2) + '%');
console.log('总收益: ' + (gains.reduce(function(a,b){ return a+b; },0) * 100).toFixed(1) + '%');

// 按年分组
var yearly = {};
sells.forEach(function(t) {
  var yr = t.date.substring(0, 4);
  if (!yearly[yr]) yearly[yr] = { w: 0, l: 0, total: 0, ret: 0 };
  yearly[yr].total++;
  yearly[yr].ret += t.ret;
  if (t.ret > 0) yearly[yr].w++;
  else yearly[yr].l++;
});

console.log('\n--- 按年度统计 ---');
Object.keys(yearly).sort().forEach(function(yr) {
  var y = yearly[yr];
  var wr = (y.w / y.total * 100).toFixed(0) + '%';
  var ret = (y.ret * 100).toFixed(1) + '%';
  console.log(yr + ': 胜率' + wr + '  收益' + ret + '  (' + y.w + '胜/' + y.l + '负)');
});
