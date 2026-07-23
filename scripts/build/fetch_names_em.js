// 从东方财富获取ETF名称和跟踪指数
var https = require('https');
var fs = require('fs');

var POOL_FILE = 'D:/QClaw_Trading/data/etf_pool.js';
var pool = require(POOL_FILE);

// 找出name=代码的ETF（需要补充名称）
var needNames = pool.filter(function(e) { return e.name === e.code || e.name === '待补充'; });
console.log('需要补充名称：' + needNames.length + '只\n');

// 东方财富基金信息接口
function fetchEtfInfo(code, market) {
  return new Promise(function(resolve) {
    // 东方财富的secid格式：1.SH代码 或 0.SZ代码
    var secid = (market === 'SH' ? '1.' : '0.') + code;
    var url = 'https://fundgz.eastmoney.com/gz/' + secid + '.html';
    
    https.get(url, {headers: {'Referer': 'https://fund.eastmoney.com/'}}, function(r) {
      var chunks = [];
      r.on('data', function(c) { chunks.push(c); });
      r.on('end', function() {
        try {
          var html = Buffer.concat(chunks).toString('utf8');
          // 从HTML中提取基金名称
          var nameMatch = html.match(/基金名称[：:]\s*<[^>]*>([^<]+)</);
          var name = nameMatch ? nameMatch[1].trim() : code;
          resolve({code: code, name: name});
        } catch(e) {
          resolve({code: code, name: code});
        }
      });
    }).on('error', function() { resolve({code: code, name: code}); });
  });
}

// 尝试从东方财富ETF行情接口获取
function fetchFromQuote(code, market) {
  return new Promise(function(resolve) {
    var secid = (market === 'SH' ? '1.' : '0.') + code;
    var url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=' + secid + '&fields=f57,f58';
    
    https.get(url, {headers: {'Referer': 'https://quote.eastmoney.com/'}}, function(r) {
      var chunks = [];
      r.on('data', function(c) { chunks.push(c); });
      r.on('end', function() {
        try {
          var raw = Buffer.concat(chunks).toString('utf8');
          var j = JSON.parse(raw);
          var data = j.data;
          if (data && data.f58) {
            resolve({code: code, name: data.f58});
          } else {
            resolve({code: code, name: code});
          }
        } catch(e) {
          resolve({code: code, name: code});
        }
      });
    }).on('error', function() { resolve({code: code, name: code}); });
  });
}

async function main() {
  console.log('开始获取名称...\n');
  var updated = 0;
  
  for (var i = 0; i < needNames.length; i++) {
    var e = needNames[i];
    
    // 先尝试quote接口
    var result = await fetchFromQuote(e.code, e.market);
    
    if (result.name === e.code) {
      // 如果失败，尝试fund接口
      result = await fetchEtfInfo(e.code, e.market);
    }
    
    if (result.name !== e.code) {
      e.name = result.name;
      updated++;
      console.log((i+1) + '/' + needNames.length + ' ✅ ' + e.code + ' → ' + e.name);
    } else {
      console.log((i+1) + '/' + needNames.length + ' ❌ ' + e.code + ' 获取失败');
    }
    
    await new Promise(function(c) { setTimeout(c, 200); });
  }

  // 保存
  var jsContent = '// ETF池 v4.3 - 补充名称\n'
    + '// 更新日期: ' + new Date().toISOString().slice(0, 10) + '\n'
    + 'module.exports = ' + JSON.stringify(pool, null, 2) + ';\n';
  fs.writeFileSync(POOL_FILE, jsContent, 'utf8');
  
  console.log('\n=== 完成 ===');
  console.log('成功补充：' + updated + '只');
  console.log('失败：' + (needNames.length - updated) + '只');
  console.log('已保存：' + POOL_FILE);
}
main();
