var https = require('https');
var fs = require('fs');

function fetchMax(code) {
  return new Promise(function(resolve) {
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + code + ',day,,,2000,qfq';
    var req = https.get(url, {headers:{'Referer':'https://gu.qq.com/'}}, function(r) {
      var chunks = [];
      r.on('data', function(s){ chunks.push(s); });
      r.on('end', function() {
        try {
          var raw = Buffer.concat(chunks).toString('utf8');
          var j = JSON.parse(raw);
          var arr = j.data && j.data[code] && j.data[code].day || [];
          resolve({ len: arr.length, first: arr[0] ? arr[0][0] : null, last: arr[arr.length-1] ? arr[arr.length-1][0] : null, arr: arr });
        } catch(e) { resolve({ len: 0, err: e.message }); }
      });
    });
    req.on('error', function(e){ resolve({ len: 0, err: e.message }); });
    req.setTimeout(15000, function(){ req.destroy(); resolve({ len: 0, err: 'timeout' }); });
  });
}

async function main() {
  console.log('下载沪深300最多条数据...');
  var result = await fetchMax('sh000300');
  console.log('实际条数:', result.len, '范围:', result.first, '~', result.last);

  if (result.len > 0 && result.arr) {
    var data = result.arr.map(function(p) {
      return { date: p[0], open: parseFloat(p[1]), close: parseFloat(p[2]),
               high: parseFloat(p[3]), low: parseFloat(p[4]), vol: parseFloat(p[5]) };
    });
    var OUT = 'D:/QClaw_Trading/data/history/sh000300.json';
    fs.writeFileSync(OUT, JSON.stringify(data, null, 2), 'utf8');
    console.log('已保存到 ' + OUT);

    // 同时更新回测脚本里的ETF目录，找到最老的数据
    var histDir = 'D:/QClaw_Trading/data/history';
    var files = fs.readdirSync(histDir).filter(function(f){ return f.endsWith('.json') && /^(sh|sz)/.test(f) && !f.match(/^sh000|^sz399|^sh001/); });
    var oldest = null;
    for (var i = 0; i < files.length; i++) {
      try {
        var raw = JSON.parse(fs.readFileSync(histDir + '/' + files[i], 'utf8'));
        if (Array.isArray(raw) && raw.length > 0) {
          var d0 = raw[0].date || (Array.isArray(raw[0]) ? raw[0][0] : null);
          if (d0 && (!oldest || d0 < oldest)) oldest = d0;
        }
      } catch(e) {}
    }
    console.log('ETF历史最早日期:', oldest);
  } else {
    console.log('下载失败:', result.err);
  }
  process.exit(0);
}
main();
