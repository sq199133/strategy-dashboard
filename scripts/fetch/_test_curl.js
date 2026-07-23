var execSync = require('child_process').execSync;
var fs = require('fs');

function curl(url) {
  try {
    return execSync(
      'curl.exe -s --max-time 10 -H "Referer: https://gu.qq.com/" --url ' + JSON.stringify(url),
      { encoding: 'utf8', timeout: 12000, windowsHide: true }
    );
  } catch(e) { return null; }
}

function fetchBars(sym) {
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + sym + ',day,,,300,qfq';
  var raw = curl(url);
  if (!raw) return [];
  try {
    var j = JSON.parse(raw);
    var data = j.data && j.data[sym];
    return (data && (data.qfqday || data.day)) || [];
  } catch(e) { return []; }
}

function convert(arr) {
  return arr.map(function(p) {
    return {
      date: p[0],
      open: Number(p[1]),
      close: Number(p[2]),
      high: Number(p[3]),
      low: Number(p[4]),
      vol: parseInt(p[5]) || 0,
      amount: Number(p[6]) || 0,
      chg: Number(p[7]) || 0
    };
  });
}

// Test a few ETFs
var codes = [
  { sym: 'sh510050', name: '50ETF' },
  { sym: 'sz159919', name: '深100ETF' },
  { sym: 'sz159592', name: 'A50ETF银华' }
];

codes.forEach(function(c) {
  process.stdout.write('Testing ' + c.name + '... ');
  var data = fetchBars(c.sym);
  if (data.length > 0) {
    var r = convert(data);
    r.sort(function(a, b) { return b.date.localeCompare(a.date); });
    console.log('OK ' + r.length + ' bars, ' + r[r.length-1].date + '~' + r[0].date);
  } else {
    console.log('FAIL');
  }
});

console.log('Test done');
