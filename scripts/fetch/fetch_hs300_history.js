// 下载沪深300历史数据（腾讯接口）
var https = require('https');
var fs    = require('fs');

var OUT = 'D:/QClaw_Trading/data/history/sh000300.json';

// 腾讯行情接口（指数用 .day 数组，ETF用 .qfqday）
function fetchTx(code, count) {
  return new Promise(function(resolve) {
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + code + ',day,,,' + count + ',qfq';
    https.get(url, {headers:{'Referer':'https://gu.qq.com/'}}, function(r) {
      var chunks = [];
      r.on('data', function(s){ chunks.push(s); });
      r.on('end', function() {
        try {
          var d = Buffer.concat(chunks).toString('utf8');
          var j = JSON.parse(d);
          // 指数：day 数组；ETF：qfqday 数组
          var arr = (j.data[code] && j.data[code].day) || (j.data[code] && j.data[code].qfqday) || [];
          var result = arr.map(function(p) {
            return {
              date:  p[0],
              open:  parseFloat(p[1]),
              close: parseFloat(p[2]),
              high:  parseFloat(p[3]),
              low:   parseFloat(p[4]),
              vol:   parseFloat(p[5])
            };
          });
          resolve(result);
        } catch(e) { resolve([]); }
      });
    }).on('error', function(){ resolve([]); });
  });
}

async function main() {
  console.log('下载沪深300（腾讯接口）...');
  var data = await fetchTx('sh000300', 5000);
  await new Promise(function(cb){setTimeout(cb,300);});
  console.log('获取：' + data.length + '条');
  if (data.length > 0) {
    console.log('范围：' + data[0].date + ' ~ ' + data[data.length-1].date);
    fs.writeFileSync(OUT, JSON.stringify(data, null, 2), 'utf8');
    console.log('已保存：' + OUT);
  } else {
    console.log('❌ 获取失败');
  }
}
main().catch(console.error);
