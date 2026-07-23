// 验证513120与推荐组合的相关性
var https = require('https');

var codes = ['159259', '515700', '513120', '513100', '511010'];

function getMarket(code) {
  if (code.startsWith('5') || code.startsWith('0')) return 'sh';
  if (code.startsWith('1')) return 'sz';
  return 'sh';
}

function fetchKline(code) {
  return new Promise(function(resolve) {
    var market = getMarket(code);
    var secid = market + code;
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,130,qfq';
    https.get(url, {headers: {'Referer': 'https://gu.qq.com'}}, function(r) {
      var chunks = [];
      r.on('data', function(c) { chunks.push(c); });
      r.on('end', function() {
        try {
          var raw = Buffer.concat(chunks).toString('utf8');
          var j = JSON.parse(raw);
          var data = j.data[secid];
          var days = data.qfqday || data.day || [];
          resolve({code: code, prices: days.map(function(d) { return parseFloat(d[2]); })});
        } catch(e) {
          resolve({code: code, prices: []});
        }
      });
    }).on('error', function() { resolve({code: code, prices: []}); });
  });
}

function pearson(a, b) {
  var n = Math.min(a.length, b.length) - 1;
  if (n < 20) return null;
  var ra = [], rb = [];
  for (var i = 1; i <= n; i++) {
    ra.push((a[i] - a[i-1]) / a[i-1]);
    rb.push((b[i] - b[i-1]) / b[i-1]);
  }
  var meanA = ra.reduce(function(s,v){return s+v;},0) / ra.length;
  var meanB = rb.reduce(function(s,v){return s+v;},0) / rb.length;
  var cov = 0, va = 0, vb = 0;
  for (var i = 0; i < ra.length; i++) {
    var da = ra[i] - meanA;
    var db = rb[i] - meanB;
    cov += da * db;
    va += da * da;
    vb += db * db;
  }
  if (va === 0 || vb === 0) return null;
  return cov / Math.sqrt(va * vb);
}

async function main() {
  var data = {};
  for (var i = 0; i < codes.length; i++) {
    var result = await fetchKline(codes[i]);
    data[codes[i]] = result.prices;
    console.log(codes[i] + ': ' + result.prices.length + '条');
    await new Promise(function(c) { setTimeout(c, 200); });
  }
  
  console.log('\n--- 推荐组合相关性矩阵 ---\n');
  console.log('         159259  515700  513120  513100  511010');
  for (var i = 0; i < codes.length; i++) {
    var line = codes[i] + '  ';
    var maxR = 0, maxJ = '';
    for (var j = 0; j < codes.length; j++) {
      if (i === j) { line += '  1.00  '; continue; }
      var r = pearson(data[codes[i]], data[codes[j]]);
      var rs = r !== null ? r.toFixed(2) : '  N/A';
      line += rs + '  ';
      if (r !== null && Math.abs(r) > Math.abs(maxR)) { maxR = r; maxJ = codes[j]; }
    }
    var status = Math.abs(maxR) <= 0.70 ? '✅' : '❌';
    console.log(line + status + ' maxCorr=' + maxR.toFixed(2) + ' (vs ' + maxJ + ')');
  }
}
main();
