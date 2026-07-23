// 计算当前5只持仓的120日相关性矩阵
var https = require('https');
var codes = ['159259', '515700', '513120', '518880', '513100'];
var names = { '159259': '成长ETF', '515700': '新能源车', '513120': '港股创新药', '518880': '黄金ETF', '513100': '纳指ETF' };

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

function calcReturns(prices) {
  var rets = [];
  for (var i = 1; i < prices.length; i++) {
    rets.push((prices[i] - prices[i-1]) / prices[i-1]);
  }
  return rets;
}

function pearson(x, y) {
  var n = Math.min(x.length, y.length);
  if (n < 30) return NaN;
  var sx = 0, sy = 0, sxy = 0, sx2 = 0, sy2 = 0;
  for (var i = 0; i < n; i++) {
    sx += x[i]; sy += y[i]; sxy += x[i]*y[i]; sx2 += x[i]*x[i]; sy2 += y[i]*y[i];
  }
  var denom = Math.sqrt((n*sx2 - sx*sx) * (n*sy2 - sy*sy));
  return denom === 0 ? 0 : (n*sxy - sx*sy) / denom;
}

(async function() {
  var results = {};
  for (var c of codes) {
    var r = await fetchKline(c);
    results[c] = calcReturns(r.prices);
    console.log(names[c] + ' (' + c + '): ' + r.prices.length + ' days, ' + results[c].length + ' returns');
  }

  console.log('\n=== Correlation Matrix (120-day daily returns) ===');
  console.log(',' + codes.map(function(c) { return names[c]; }).join(','));
  for (var i = 0; i < codes.length; i++) {
    var row = [names[codes[i]]];
    for (var j = 0; j < codes.length; j++) {
      var r = pearson(results[codes[i]], results[codes[j]]);
      row.push(r.toFixed(2));
    }
    console.log(row.join(','));
  }

  // Max corr per holding
  console.log('\n=== Max Corr vs Others ===');
  for (var i = 0; i < codes.length; i++) {
    var maxR = 0;
    for (var j = 0; j < codes.length; j++) {
      if (i !== j) {
        var r = Math.abs(pearson(results[codes[i]], results[codes[j]]));
        if (r > maxR) maxR = r;
      }
    }
    console.log(names[codes[i]] + ': maxCorr=' + maxR.toFixed(2));
  }
})();
