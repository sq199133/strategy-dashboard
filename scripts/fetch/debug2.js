var https = require('https');
var fs = require('fs');

var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,day,,,300,qfq';
var OUT = 'D:/QClaw_Trading/data/history/sh000300.json';

console.log('开始请求...');

var req = https.get(url, {headers:{'Referer':'https://gu.qq.com/'}}, function(r) {
  console.log('状态码:', r.statusCode);
  var chunks = [];
  r.on('data', function(c){ chunks.push(c); });
  r.on('end', function() {
    console.log('接收完毕，字节数:', chunks.length);
    var raw = Buffer.concat(chunks).toString('utf8');
    console.log('JSON长度:', raw.length);
    console.log('前100字符:', raw.slice(0, 100));
    try {
      var j = JSON.parse(raw);
      console.log('解析成功，data keys:', Object.keys(j.data || {}));
      var obj = j.data['sh000300'];
      console.log('sh000300 keys:', obj ? Object.keys(obj) : '不存在');
      var arr = obj && (obj.day || obj.qfqday);
      console.log('K线数组长度:', arr ? arr.length : 0);
      if (arr && arr.length > 0) {
        var result = arr.map(function(p) {
          return { date: p[0], open: parseFloat(p[1]), close: parseFloat(p[2]),
                   high: parseFloat(p[3]), low: parseFloat(p[4]), vol: parseFloat(p[5]) };
        });
        fs.writeFileSync(OUT, JSON.stringify(result, null, 2), 'utf8');
        console.log('已保存 ' + result.length + ' 条到 ' + OUT);
      }
    } catch(e) {
      console.log('JSON解析失败:', e.message);
    }
    process.exit(0);
  });
});

req.on('error', function(e) {
  console.log('网络错误:', e.message);
  process.exit(1);
});

req.setTimeout(12000, function() {
  console.log('请求超时');
  req.destroy();
  process.exit(1);
});
