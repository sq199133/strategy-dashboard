const https = require('https');

const CODES = [
  {code:'sh000001', name:'上证指数'},
  {code:'sz399006', name:'创业板指'},
  {code:'sz399300', name:'沪深300'},
  {code:'sh510300', name:'沪深300ETF'},
  {code:'sz159915', name:'创业板ETF'},
  {code:'sh512480', name:'半导体ETF'},
  {code:'sh512220', name:'TMTETF'},
  {code:'sh516390', name:'新能源汽车ETF'},
  {code:'sh513100', name:'纳指ETF'},
  {code:'sh159338', name:'中证A500'},
  {code:'sh588080', name:'科创50ETF易方达'},
  {code:'sz561370', name:'新能源车ETF'},
  {code:'sz159566', name:'储能电池'},
];

function fetch(code) {
  return new Promise(function(resolve) {
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=x&param='+code+',day,2026-03-01,2027-01-01,60,qfq';
    https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(r) {
      var d = '';
      r.on('data', function(s){ d += s; });
      r.on('end', function(){
        try {
          var txt = d.replace(/^[^=]+=/, '');
          var j = JSON.parse(txt);
          var key = Object.keys(j.data)[0];
          var arr = j.data[key].qfqday || j.data[key].day || [];
          resolve(arr);
        } catch(e) { resolve([]); }
      });
    }).on('error', function(){ resolve([]); });
  });
}

async function run() {
  var results = {};
  for (var i = 0; i < CODES.length; i++) {
    var item = CODES[i];
    var arr = await fetch(item.code);
    if (arr.length > 0) {
      var last = arr[arr.length-1];
      var prev = arr.length >= 2 ? arr[arr.length-2] : last;
      results[item.name] = {
        date: last[0],
        close: parseFloat(last[2]),
        chg: parseFloat(last[2]) - parseFloat(prev[2]),
        chgPct: ((parseFloat(last[2]) - parseFloat(prev[2])) / parseFloat(prev[2]) * 100).toFixed(2)
      };
    }
    await new Promise(function(r){ setTimeout(r, 200); });
  }
  console.log(JSON.stringify(results, null, 2));
}

run();
