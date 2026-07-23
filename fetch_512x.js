const https = require('https');

const ITEMS = [
  {code:'sh512270', name:'登录精选ETF'},
  {code:'sh512220', name:'TMTETF'},
];

function fetch(code) {
  return new Promise(function(resolve) {
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=x&param='+code+',day,2025-10-01,2027-01-01,120,qfq';
    https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(r) {
      var d = '';
      r.on('data', function(s){ d += s; });
      r.on('end', function(){
        try {
          var j = JSON.parse(d.replace(/^[^=]+=/, ''));
          var arr = j.data[Object.keys(j.data)[0]].qfqday || [];
          var closes = arr.map(function(p){ return parseFloat(p[2]); });
          console.log(JSON.stringify({code:code, last:arr[arr.length-1], closes:closes}));
        } catch(e) { console.log(JSON.stringify({code:code, err:e.message})); }
        resolve();
      });
    }).on('error', function(){ console.log(JSON.stringify({code:code, err:'net'})); resolve(); });
  });
}

async function run() {
  for (var i = 0; i < ITEMS.length; i++) {
    await fetch(ITEMS[i].code);
    await new Promise(function(r){ setTimeout(r, 400); });
  }
}
run();
