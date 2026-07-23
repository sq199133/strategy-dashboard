// 计算推荐组合的两两相关性
var https = require('https');
var fs = require('fs');

// 候选组合
var candidates = ['159259', '515700', '159602', '513100', '511010'];
// 对比：当前持仓
var current = ['159681', '512770', '512220', '516390', '513100'];

// 市场前缀
function getMarket(code) {
  if (code.startsWith('5') || code.startsWith('0')) return 'sh';
  if (code.startsWith('1')) return 'sz';
  return 'sh';
}

// 获取K线
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

// Pearson相关系数（日收益率）
function pearson(a, b) {
  var n = Math.min(a.length, b.length) - 1;
  if (n < 20) return null;
  // 日收益率
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
  console.log('=== 推荐组合相关性分析 ===\n');
  
  // 获取所有候选数据
  var allCodes = [...new Set(candidates.concat(current))];
  var data = {};
  
  for (var i = 0; i < allCodes.length; i++) {
    var result = await fetchKline(allCodes[i]);
    data[allCodes[i]] = result.prices;
    console.log(allCodes[i] + ': ' + result.prices.length + '条K线');
    await new Promise(function(c) { setTimeout(c, 200); });
  }
  
  // 推荐组合相关性矩阵
  console.log('\n--- 推荐组合：159259/515700/159602/513100/511010 ---\n');
  for (var i = 0; i < candidates.length; i++) {
    var line = candidates[i] + '\t';
    for (var j = 0; j < candidates.length; j++) {
      if (i === j) { line += '  1.00'; continue; }
      var r = pearson(data[candidates[i]], data[candidates[j]]);
      line += (r !== null ? r.toFixed(2) : '  N/A') + ' ';
    }
    console.log(line);
  }
  
  // 当前持仓相关性矩阵
  console.log('\n--- 当前持仓：159681/512770/512220/516390/513100 ---\n');
  for (var i = 0; i < current.length; i++) {
    var line = current[i] + '\t';
    for (var j = 0; j < current.length; j++) {
      if (i === j) { line += '  1.00'; continue; }
      var r = pearson(data[current[i]], data[current[j]]);
      line += (r !== null ? r.toFixed(2) : '  N/A') + ' ';
    }
    console.log(line);
  }
  
  // 检查推荐组合是否满足maxCorr<=0.70
  console.log('\n--- 推荐组合maxCorr检查 ---\n');
  var maxCorrs = {};
  for (var i = 0; i < candidates.length; i++) {
    var maxR = 0, maxJ = '';
    for (var j = 0; j < candidates.length; j++) {
      if (i === j) continue;
      var r = pearson(data[candidates[i]], data[candidates[j]]);
      if (r !== null && Math.abs(r) > Math.abs(maxR)) {
        maxR = r;
        maxJ = candidates[j];
      }
    }
    maxCorrs[candidates[i]] = {corr: maxR, with: maxJ};
    var status = Math.abs(maxR) <= 0.70 ? '✅' : '❌';
    console.log(status + ' ' + candidates[i] + ' maxCorr=' + maxR.toFixed(2) + ' (vs ' + maxJ + ')');
  }
}
main();
