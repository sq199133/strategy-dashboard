// 快速获取指数数据
var https = require('https');

var targets = [
  { code: 'sh000001', name: '上证指数' },
  { code: 'sz399006', name: '创业板指' },
  { code: 'sh000300', name: '沪深300' },
  { code: 'sh000688', name: '科创50' },
  { code: 'sz399001', name: '深证成指' },
  { code: 'sh000016', name: '上证50' },
  { code: 'sh000905', name: '中证500' },
  { code: 'sz399333', name: '恒生指数' }
];

function fetchKline(code) {
  return new Promise(function(resolve) {
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + code + ',day,,,25,qfq';
    https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(r) {
      var chunks = [];
      r.on('data', function(c){chunks.push(c);});
      r.on('end', function(){
        try {
          var raw = Buffer.concat(chunks).toString('utf8');
          var j = JSON.parse(raw);
          var data = j.data[code];
          var days = data.qfqday || data.day || [];
          var close = parseFloat(days[days.length-1][2]);
          var prev = parseFloat(days[days.length-2][2]);
          var closes = days.map(function(d){return parseFloat(d[2]);});
          var ma20 = closes.slice(-20).reduce(function(s,v){return s+v;},0)/20;
          var maDir = closes[closes.length-1] > closes[closes.length-20] ? '↗' : '↘';
          var pct1 = ((close/prev)-1)*100;
          var pct20 = ((close/closes[closes.length-20])-1)*100;
          resolve({close:close, prev:prev, pct1:pct1, pct5:((close/closes[closes.length-5])-1)*100, pct20:pct20, ma20:ma20, maDir:maDir});
        } catch(e){resolve(null);}
      });
    }).on('error', function(){resolve(null);});
  });
}

async function main() {
  console.log('=== 2026-04-20 主要指数 ===\n');
  for (var i = 0; i < targets.length; i++) {
    var t = targets[i];
    var d = await fetchKline(t.code);
    if (d) {
      var above = d.close > d.ma20 ? '上' : '下';
      console.log(t.name + ' 收=' + d.close.toFixed(2) + ' MA20=' + d.ma20.toFixed(2) + d.maDir + ' 零轴' + above + ' 5日' + d.pct5.toFixed(2) + '% 20日' + d.pct20.toFixed(2) + '%');
    } else {
      console.log(t.name + ' ❌');
    }
    await new Promise(function(c){setTimeout(c,200);});
  }
}
main();
