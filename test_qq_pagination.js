var https = require('https');

// 测试510300（2012年成立，更老的ETF）和分页
var codes = ['sh159338', 'sh510300', 'sh512480'];
var results = {};

codes.forEach(function(code){
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param=' + code + ',day,2012-01-01,2025-12-31,300,qfq&r=0.1';
  var req = https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(res){
    var d='';
    res.on('data',c=>d+=c);
    res.on('end',function(){
      var ticker = code;
      var txt = d.replace(/^[^=]+=/,'');
      try {
        var j = JSON.parse(txt);
        var key = Object.keys(j.data)[0];
        var data = j.data[key].qfqday || j.data[key].day;
        var allCount = j.data[key].dataCount || data.length;
        console.log(ticker + ': 共' + data.length + '条, API报告总数:' + allCount + ', 首:' + data[0][0] + ', 末:' + data[data.length-1][0]);
        // 检查是否有分页提示
        var info = j.data[key];
        console.log('  keys:', Object.keys(info).join(', '));
        if (info.qfqdayqfq) console.log('  qfqdayqfq:', info.qfqdayqfq.length);
      } catch(e) {
        console.log(ticker + '失败:', e.message);
      }
    });
  });
  req.on('error', function(e){ console.log(code + '网络错误:', e.message); });
});

// 测试腾讯的另一个历史K线接口（可能支持更多条数）
console.log('\n--- 测试东方财富历史K线 ---');
var emUrl = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?cb=jQuery&secid=1.159338&ut=&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=1&beg=20100101&end=20251231&smplmt=460&lmt=1000000';
https.get(emUrl, {headers:{'Referer':'https://quote.eastmoney.com', 'User-Agent':'Mozilla/5.0'}}, function(res){
  var d='';
  res.on('data',c=>d+=d+=c);
  res.on('end',function(){
    var m = d.match(/jQuery\(([\s\S]+)\)/);
    if (!m) { console.log('EM: 解析失败, 原始:', d.slice(0,200)); return; }
    try {
      var j = JSON.parse(m[1]);
      var klines = j.data.klines || [];
      console.log('EM K线总数:', klines.length);
      if (klines.length > 0) console.log('  首:', klines[0], '  末:', klines[klines.length-1]);
    } catch(e) { console.log('EM解析失败:', e.message); }
  });
}).on('error', function(e){ console.log('EM网络错误:', e.message); });
