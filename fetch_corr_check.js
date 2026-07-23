// 检查510500中证500ETF和相关持仓的历史相关性（真实Pearson）
const https = require('https');

// 所有ETF都用{market:'sh'/'sz', code:'5xxxxx'}格式
const CODES = [
  {market:'sh', code:'510500', name:'中证500ETF南方'},
  {market:'sz', code:'159681', name:'创业板50ETF'},
  {market:'sh', code:'512770', name:'战略新兴ETF华夏'},
  {market:'sh', code:'512220', name:'TMTETF景顺'},
  {market:'sz', code:'516390', name:'新能源汽车ETF'},
  {market:'sh', code:'513100', name:'纳指ETF国泰'},
];

function emKline(market, code, count) {
  return new Promise(function(resolve) {
    var secid = (market === 'sh' ? '1.' : '0.') + code;
    var url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' +
      'secid=' + secid +
      '&fields1=f1,f2,f3,f4,f5,f6' +
      '&fields2=f51,f52,f53,f54,f55,f56,f57,f58' +
      '&klt=101&fqt=1&beg=20250101&end=20991231&lmt=' + (count||120);
    https.get(url, {
      headers:{'Referer':'https://quote.eastmoney.com','User-Agent':'Mozilla/5.0'}
    }, function(r) {
      var d=''; r.on('data',function(s){d+=s;});
      r.on('end',function(){
        try {
          var j=JSON.parse(d);
          var klines=j.data?(j.data.klines||[]):[];
          var recs=klines.map(function(l){
            var p=l.split(',');
            return {date:p[0],close:parseFloat(p[2])};
          });
          resolve(recs);
        } catch(e){ resolve([]); }
      });
    }).on('error',function(){ resolve([]); });
  });
}

// Pearson相关系数
function pearson(x, y) {
  if (x.length < 10) return null;
  var n = x.length;
  var mx=0,my=0;
  for(var i=0;i<n;i++){mx+=x[i];my+=y[i];}
  mx/=n;my/=n;
  var cov=0,sx=0,sy=0;
  for(var i=0;i<n;i++){
    var dx=x[i]-mx,dy=y[i]-my;
    cov+=dx*dy;sx+=dx*dx;sy+=dy*dy;
  }
  var den=Math.sqrt(sx*sy);
  return den===0?null:cov/den;
}

// 日收益率序列
function returns(arr) {
  var r=[];
  for(var i=1;i<arr.length;i++){
    r.push((arr[i].close-arr[i-1].close)/arr[i-1].close);
  }
  return r;
}

// 两数组共同部分
function commonReturns(arr1, arr2) {
  var s2 = new Set(arr2.map(function(v){return v.date;}));
  var common1=[], common2=[];
  for(var i=1;i<arr1.length;i++){
    if(s2.has(arr1[i].date)){
      common1.push((arr1[i].close-arr1[i-1].close)/arr1[i-1].close);
      var prev=arr2.find(function(v){return v.date===arr1[i].date;});
      var prevPrev=arr2.find(function(v){return v.date===arr1[i-1].date;});
      if(prev&&prevPrev){
        common2.push((prev.close-prevPrev.close)/prevPrev.close);
      }
    }
  }
  return {r1:common1,r2:common2,len:common1.length};
}

async function run() {
  var data={};
  for(var i=0;i<CODES.length;i++){
    var c=CODES[i];
    var recs=await emKline(c.market,c.code);
    if(recs.length>0){
      data[c.market+c.code]={name:c.name,recs:recs};
      var last=recs[recs.length-1];
      console.log('✅ '+c.name+'  '+recs.length+'条  末:'+last.date+'  收:'+last.close);
    } else {
      console.log('❌ '+c.name+' 无数据');
    }
    await new Promise(function(r){setTimeout(r,500);});
  }

  var keys=Object.keys(data);
  console.log('\n━━━ Pearson相关矩阵 ━━━');

  // 表头
  var h='               |';
  keys.forEach(function(k){h+=' '+(data[k].name||k).substring(0,6).padEnd(8)+'|';});
  console.log(h);
  console.log('-'.repeat(h.length));

  for(var i=0;i<keys.length;i++){
    var row=(data[keys[i]].name||keys[i]).substring(0,14).padEnd(14)+'|';
    for(var j=0;j<keys.length;j++){
      if(i===j){row+='  1.000  | ';} else {
        var r=pearson(returns(data[keys[i]].recs),returns(data[keys[j]].recs));
        if(r===null){row+='  N/A   | ';} else {
          var m=r>0.7?'🔴':r>0.5?'🟡':r>0.3?'🟢':'⚪';
          row+=m+' '+r.toFixed(3)+'| ';
        }
      }
    }
    console.log(row);
  }

  console.log('\n图例: 🔴>0.70  🟡0.50-0.70  🟢0.30-0.50  ⚪<0.30');

  // 重点：510500与其他持仓
  console.log('\n━━━ 510500(中证500) vs 各持仓 ━━━');
  var base='sh510500';
  keys.forEach(function(k){
    if(k===base)return;
    var p=pearson(returns(data[base].recs),returns(data[k].recs));
    if(p!==null){
      var days=Math.min(data[base].recs.length,data[k].recs.length);
      var note=p>0.7?'🔴高度重叠!':p>0.5?'🟡中高相关':p>0.3?'🟢中低相关':'⚪低相关';
      console.log('  '+data[k].name.padEnd(12)+' r='+p.toFixed(3)+' '+note+'  (共同:'+days+'日)');
    }
  });
}

run().catch(function(e){console.error(e);process.exit(1);});
