var https = require('https');
var fs = require('fs');

var OUT = 'D:/QClaw_Trading/data/history/sh000300.json';

function fetch(code, count) {
  return new Promise(function(resolve) {
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + code + ',day,,,' + count + ',qfq';
    var req = https.get(url, {headers:{'Referer':'https://gu.qq.com/'}}, function(r) {
      var chunks = [];
      r.on('data', function(s){ chunks.push(s); });
      r.on('end', function() {
        try {
          var raw = Buffer.concat(chunks).toString('utf8');
          var j = JSON.parse(raw);
          var dataObj = j.data[code];
          if (!dataObj) { console.log('无数据对象'); resolve([]); return; }
          var keys = Object.keys(dataObj);
          console.log('keys:', keys.join(','));
          // 尝试各种可能的数组键
          var arr = dataObj.day || dataObj.qfqday || dataObj.data || [];
          console.log('数组长度:', arr.length);
          if (arr.length > 0) {
            console.log('首条:', JSON.stringify(arr[0]));
            var result = arr.map(function(p) {
              return { date: p[0], open: parseFloat(p[1]), close: parseFloat(p[2]),
                       high: parseFloat(p[3]), low: parseFloat(p[4]), vol: parseFloat(p[5]) };
            });
            fs.writeFileSync(OUT, JSON.stringify(result, null, 2), 'utf8');
            console.log('已保存 ' + result.length + ' 条到 ' + OUT);
            resolve(result);
          } else {
            console.log('数组为空');
            resolve([]);
          }
        } catch(e) {
          console.log('解析错误:', e.message);
          resolve([]);
        }
      });
    });
    req.on('error', function(e){ console.log('错误:', e.message); resolve([]); });
    req.setTimeout(12000, function(){ console.log('超时'); req.destroy(); resolve([]); });
  });
}

async function main() {
  var data = await fetch('sh000300', 3000);
  process.exit(0);
}
main();
