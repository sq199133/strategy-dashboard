var fs = require('fs');
var raw = JSON.parse(fs.readFileSync('D:/QClaw_Trading/scripts/backtest/backtest_20y_trades.json', 'utf8'));
var buys = raw.filter(function(t){ return t.action === 'BUY'; });
var sells = raw.filter(function(t){ return t.action === 'SELL'; });
var gains = sells.map(function(s){ return s.ret; }).filter(function(r){ return r !== undefined; });

console.log('=== 沪深300 MA20+MACD 20年回测交易分析 ===');
console.log('交易总数: ' + raw.length);
console.log('买入次数: ' + buys.length + '  卖出次数: ' + sells.length);
console.log('有效卖出: ' + gains.length);

var wins = gains.filter(function(r){ return r > 0; });
var losses = gains.filter(function(r){ return r <= 0; });

console.log('\n--- 单次买卖胜率 ---');
console.log('盈利交易: ' + wins.length);
console.log('亏损交易: ' + losses.length);
console.log('胜率: ' + (wins.length / gains.length * 100).toFixed(1) + '%');
console.log('平均盈利: ' + (wins.reduce(function(a,b){ return a+b; }, 0) / wins.length).toFixed(2) + '%');
console.log('平均亏损: ' + (losses.reduce(function(a,b){ return a+b; }, 0) / losses.length).toFixed(2) + '%');
console.log('盈亏比: ' + Math.abs((wins.reduce(function(a,b){ return a+b; },0)/wins.length) / (losses.reduce(function(a,b){ return a+b; },0)/losses.length)).toFixed(2));

// 分段胜率
var byYear = {};
gains.forEach(function(r, i) {
  var sellTrades = sells.filter(function(s){ return s.ret !== undefined; });
});
// 按年度分组
var yearly = {};
for (var i = 0; i < sells.length; i++) {
  var t = sells[i];
  if (t.ret === undefined) continue;
  var yr = t.date.substring(0, 4);
  if (!yearly[yr]) yearly[yr] = { wins: 0, losses: 0, total: 0 };
  yearly[yr].total++;
  if (t.ret > 0) yearly[yr].wins++;
  else yearly[yr].losses++;
}

console.log('\n--- 按年度胜率 ---');
Object.keys(yearly).sort().forEach(function(yr) {
  var y = yearly[yr];
  var wr = y.total > 0 ? (y.wins / y.total * 100).toFixed(0) + '%' : '-';
  console.log(yr + ': ' + wr + ' (' + y.wins + '/' + y.total + ')');
});

// 总结
console.log('\n--- 收益汇总 ---');
var result = JSON.parse(fs.readFileSync('D:/QClaw_Trading/scripts/backtest/backtest_20y_result.json', 'utf8'));
console.log('初始资金: ' + result.initial.toLocaleString());
console.log('最终资金: ' + result.final.toLocaleString());
console.log('总收益: ' + (result.total_return * 100).toFixed(1) + '%');
console.log('年化收益: ' + (result.annual_return * 100).toFixed(1) + '%');
console.log('最大回撤: ' + (result.max_drawdown * 100).toFixed(1) + '%');
console.log('夏普比率: ' + result.sharpe.toFixed(2));
console.log('持仓天数: ' + result.n_trades);
