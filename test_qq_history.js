var https = require('https');
var code = 'sh159338';

var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param=sh159338,day,2024-01-01,2025-12-31,300,qfq&r=0.1';
console.log('测试:', url);

var req = https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(res){
  var d='';
  res.on('data',c=>d+=c);
  res.on('end',function(){
    console.log('原始响应长度:', d.length);
    var txt = d.replace(/^[^=]+=/,'');
    try {
      var j = JSON.parse(txt);
      var key = Object.keys(j.data)[0];
      var data = j.data[key].qfqday || j.data[key].day;
      console.log('总数:', data.length);
      console.log('首条:', JSON.stringify(data[0]));
      console.log('末条:', JSON.stringify(data[data.length-1]));
    } catch(e) {
      console.log('解析失败:', e.message);
      console.log('原始前500字:', d.slice(0,500));
    }
  });
});
req.on('error', function(e){ console.log('网络错误:', e.message); });
req.setTimeout(8000, function(){ console.log('超时'); req.abort(); });
