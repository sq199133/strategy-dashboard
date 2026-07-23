// Find working codes for US index ETFs via Tencent API
'use strict';
var https = require('https');

// Try Tencent API with various US-related ETF codes
var codes = [
  'sz159934', // 标普500ETF (if exists)
  'sz513500', // 标普500ETF
  'sh513500', // might be SH
  'sz513100', // 纳指ETF (known to work)
];

async function testTx(code) {
  var secid = code;
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,5,qfq';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(5000) });
    var j = await r.json();
    var d = j.data && j.data[secid];
    var n = d ? (d.qfqday || d.day || []).length : -1;
    var name = d ? (d.qt[code] ? d.qt[code].name : '?') : '?';
    console.log(code + ' => ' + n + '条 name=' + name);
    if (n > 0) {
      var arr = d.qfqday || d.day;
      console.log('  latest: ' + arr[arr.length - 1]);
    }
  } catch(e) { console.log(code + ' => ERR: ' + e.message); }
}

// Also try fetching from sina for more US indices
function testSinaBatch() {
  var codes2 = ['int_sp500','int_dji','int_ndx','int_ftse','int_dax','int_nikkei','int_hangseng'];
  var options = {
    hostname: 'hq.sinajs.cn',
    path: '/list=' + codes2.join(','),
    headers: { 'Referer': 'https://finance.sina.com.cn/', 'User-Agent': 'Mozilla/5.0' }
  };
  https.get(options, function(r) {
    var d = '';
    r.on('data', function(c) { d += c; });
    r.on('end', function() {
      d.trim().split('\n').forEach(function(l) {
        var m = l.match(/var hq_str_(\w+)="([^"]*)"/);
        if (m && m[2]) console.log('sina ' + m[1] + ' => ' + Buffer.from(m[2], 'binary').toString('utf8').substring(0, 60));
        else if (m) console.log('sina ' + m[1] + ' => (empty)');
      });
    });
  });
}

async function main() {
  console.log('=== Tencent API (US index ETFs) ===');
  for (var c of codes) await testTx(c);
  
  // Also test 标普500 related codes
  console.log('\n=== More Tencent codes ===');
  var more = ['sh513500','sh513100','sz513500','sz159932','sh159934'];
  for (var c2 of more) await testTx(c2);
  
  console.log('\n=== Sina Finance (global indices) ===');
  testSinaBatch();
}

main();
