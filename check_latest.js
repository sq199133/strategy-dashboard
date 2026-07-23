var https = require('https');
var codes = ['sh510300', 'sh512480', 'sh159338'];

codes.forEach(function(code){
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=x&param=' + code + ',day,2025-12-01,2027-01-01,30,qfq';
  https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(r){
    var d='';
    r.on('data',c=>d+=c);
    r.on('end',function(){
      try {
        var txt = d.replace(/^[^=]+=/,'');
        var j = JSON.parse(txt);
        var key = Object.keys(j.data)[0];
        var arr = j.data[key].qfqday || j.data[key].day;
        console.log(key + ': 末=' + arr[arr.length-1].join(',') + '  共' + arr.length + '条');
      } catch(e){ console.log(code + ' err: ' + e.message); }
    });
  }).on('error', function(e){ console.log(code + ' net err'); });
});
