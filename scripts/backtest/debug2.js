var fs = require('fs');
var path = require('path');
var DATA_DIR = 'D:/QClaw_Trading/data/history';

var files = fs.readdirSync(DATA_DIR).filter(function(x){ return x.endsWith('.json'); });
console.log('总文件:', files.length);

var h = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'sh000300.json'), 'utf8'));
console.log('hs300:', h.length, '首:', h[0].date, '末:', h[h.length-1].date);

var ef = files.filter(function(x){
  return /^(sh|sz)/.test(x) && !/^sh000/.test(x) && !/^sz399/.test(x) && !/^sh001/.test(x);
});
console.log('etf文件数:', ef.length);
console.log('前5个:', ef.slice(0,5).join(', '));

// 第一个etf
var e = ef[0];
var r = JSON.parse(fs.readFileSync(path.join(DATA_DIR, e), 'utf8'));
console.log('\n第一个ETF:', e, 'len:', r.length);
console.log('首条:', JSON.stringify(r[0]));
console.log('末条:', JSON.stringify(r[r.length-1]));

// pct20
if (r.length >= 25) {
  var today = r[r.length-1].close;
  var n20 = r[r.length-25].close;
  console.log('pct20:', ((today-n20)/n20*100).toFixed(2)+'%');
}

// 检查hs300最后几个日期
console.log('\nhs300最后10天:');
for (var i = h.length-10; i < h.length; i++) {
  console.log('  ' + h[i].date);
}

// 检查etf最后几个日期
console.log('\n第一个ETF最后10天:');
for (var i = r.length-10; i < r.length; i++) {
  console.log('  ' + r[i].date);
}
