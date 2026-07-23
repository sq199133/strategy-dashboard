// 快速调试：检查ETF文件格式和日期匹配
var fs = require('fs');
var path = require('path');
var DATA_DIR = 'D:/QClaw_Trading/data/history';

var files = fs.readdirSync(DATA_DIR).filter(function(f){ return f.endsWith('.json'); });
console.log('总文件:', files.length);

var hs300 = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'sh000300.json'), 'utf8'));
console.log('沪深300:', hs300.length, '条', hs300[0].date, '~', hs300[hs300[hs300.length-1].date);

// 检查前3个ETF文件
var etfFiles = files.filter(function(f){
  return /^(sh|sz)/.test(f) && !/^sh000/.test(f) && !/^sz399/.test(f) && !/^sh001/.test(f);
});
console.log('ETF文件数:', etfFiles.length);

for (var i = 0; i < Math.min(3, etfFiles.length); i++) {
  var fname = etfFiles[i];
  var code = fname.replace('.json', '');
  var raw = JSON.parse(fs.readFileSync(path.join(DATA_DIR, fname), 'utf8'));
  console.log('\n文件:', fname, '-> 代码:', code, '-> JSON条数:', raw.length);
  console.log('  首条类型:', typeof raw[0]);
  console.log('  首条数据:', JSON.stringify(raw[0]));
  console.log('  末条数据:', JSON.stringify(raw[raw.length-1]));

  // 测试pct20计算
  if (raw.length >= 25) {
    var today = raw[raw.length-1].close;
    var nDayAgo = raw[raw.length-25].close;
    console.log('  pct20:', ((today-nDayAgo)/nDayAgo*100).toFixed(2)+'%');
  }
}

// 检查日期范围
console.log('\n=== 日期范围检查 ===');
for (var i = 0; i < Math.min(5, etfFiles.length); i++) {
  var fname = etfFiles[i];
  var raw = JSON.parse(fs.readFileSync(path.join(DATA_DIR, fname), 'utf8'));
  var firstDate = raw[0].date;
  var lastDate = raw[raw.length-1].date;
  console.log(fname + ': ' + raw.length + '条  ' + firstDate + ' ~ ' + lastDate);
}

// 检查沪深300日期
console.log('\n沪深300末50条日期:');
for (var i = hs300.length-10; i < hs300.length; i++) {
  console.log('  ' + hs300[i].date);
}
