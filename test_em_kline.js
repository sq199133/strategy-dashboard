var https = require('https');

// 腾讯K线：每请求最多300条，老ETF需要分页
// 策略：从ETF成立日开始，每300条往后翻页
// ETF格式：sh=上交所, sz=深交所
// 字段: [日期, 开, 收, 高, 低, 成交量]

// 测试东方财富K线接口（支持大量数据）
function testEM(code, market, startDate, endDate) {
  return new Promise(function(resolve){
    // secid: 1=上交所, 0=深交所
    var secid = market === 'SH' ? '1.' + code : '0.' + code;
    var url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=' + secid + '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=1&beg=' + startDate.replace(/-/g,'') + '&end=' + endDate.replace(/-/g,'') + '&lmt=5000';
    
    var req = https.get(url, {
      headers:{'Referer':'https://quote.eastmoney.com', 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    }, function(res){
      var d='';
      res.on('data',c=>d+=c);
      res.on('end',function(){
        try {
          var j = JSON.parse(d);
          var klines = j.data.klines || [];
          console.log('EM ' + code + ': ' + klines.length + '条, 首:' + (klines[0]||'?') + ', 末:' + (klines[klines.length-1]||'?'));
          resolve(klines);
        } catch(e) {
          console.log('EM ' + code + ' 失败: ' + e.message + ', d=' + d.slice(0,100));
          resolve([]);
        }
      });
    });
    req.on('error', function(e){ console.log('EM ' + code + ' 网络错误:', e.message); resolve([]); });
    req.setTimeout(10000, function(){ req.abort(); resolve([]); });
  });
}

// 测试510300（2012年成立的老ETF）
console.log('=== 测试东方财富K线接口 ===\n');
testEM('510300', 'SH', '20120101', '20251231').then(function(klines){
  if (klines.length > 0) {
    console.log('  样本[0]:', klines[0]);
    console.log('  样本[-1]:', klines[klines.length-1]);
  }
});
