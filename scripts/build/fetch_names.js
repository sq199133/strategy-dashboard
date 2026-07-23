// 为新ETF补充名称
var https = require('https');
var fs = require('fs');

var POOL_FILE = 'D:/QClaw_Trading/data/etf_pool.js';
var pool = require(POOL_FILE);

// 找出name='待补充'的ETF
var needNames = pool.filter(function(e) { return e.name === '待补充'; });
console.log('需要补充名称：' + needNames.length + '只');

// 从腾讯行情接口获取名称
function fetchName(code, market) {
  return new Promise(function(resolve) {
    var secid = market + code;
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,1,qfq';
    https.get(url, {headers: {'Referer': 'https://gu.qq.com'}}, function(r) {
      var chunks = [];
      r.on('data', function(c) { chunks.push(c); });
      r.on('end', function() {
        try {
          var raw = Buffer.concat(chunks).toString('utf8');
          var j = JSON.parse(raw);
          // 尝试从qt字段获取名称
          var qt = j.data && j.data[secid] && j.data[secid].qt;
          if (qt && qt[1]) {
            resolve({code: code, name: qt[1]});
          } else {
            // 尝试其他字段
            var info = j.data && j.data[secid];
            resolve({code: code, name: info ? (info.name || code) : code});
          }
        } catch(e) {
          resolve({code: code, name: code});
        }
      });
    }).on('error', function() { resolve({code: code, name: code}); });
  });
}

async function main() {
  console.log('\n开始获取名称...\n');
  for (var i = 0; i < needNames.length; i++) {
    var e = needNames[i];
    var result = await fetchName(e.code, e.market);
    e.name = result.name;
    console.log((i+1) + '/' + needNames.length + ' ' + e.code + ' → ' + e.name);
    await new Promise(function(c) { setTimeout(c, 300); });
  }

  // 保存
  var jsContent = '// ETF池 v4.3 - 新增' + needNames.length + '只\n'
    + '// 更新日期: ' + new Date().toISOString().slice(0, 10) + '\n'
    + 'module.exports = ' + JSON.stringify(pool, null, 2) + ';\n';
  fs.writeFileSync(POOL_FILE, jsContent, 'utf8');
  console.log('\n已保存：' + POOL_FILE);
}
main();
