const https = require('https');

const ITEMS = ['512270','512220','512770','512480'];

function fetchEM(code) {
  return new Promise(function(resolve) {
    // 512270: 上交所1.512270
    var secid = '1.' + code;
    var url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' +
      'secid=' + secid +
      '&fields1=f1,f2,f3,f4,f5,f6' +
      '&fields2=f51,f52,f53,f54,f55,f56,f57,f58' +
      '&klt=101&fqt=1&beg=20250101&end=20991231&lmt=120';

    https.get(url, {
      headers:{'Referer':'https://quote.eastmoney.com','User-Agent':'Mozilla/5.0'}
    }, function(r) {
      var d = '';
      r.on('data', function(s){ d += s; });
      r.on('end', function(){
        try {
          var j = JSON.parse(d);
          var klines = j.data ? (j.data.klines || []) : [];
          var closes = klines.map(function(line){
            var p = line.split(',');
            return parseFloat(p[2]);
          });
          var lastDate = klines.length > 0 ? klines[klines.length-1].split(',')[0] : '无';
          console.log(code + '|' + lastDate + '|' + klines.length + '条|' + closes.slice(-5).join(','));
        } catch(e) { console.log(code + '|ERR:' + e.message); }
        resolve();
      });
    }).on('error', function(){ console.log(code + '|NETERR'); resolve(); });
  });
}

async function run() {
  for (var i = 0; i < ITEMS.length; i++) {
    await fetchEM(ITEMS[i]);
    await new Promise(function(r){ setTimeout(r, 300); });
  }
}
run();
