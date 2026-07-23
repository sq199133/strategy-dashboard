// 用腾讯接口获取真实K线数据计算相关性
const https = require('https');
const codes = [
  {code:'sh510500', name:'中证500ETF南方'},
  {code:'sh512770', name:'战略新兴ETF华夏'},
  {code:'sh512220', name:'TMTETF景顺'},
  {code:'sh159681', name:'创业板50ETF'},
  {code:'sh516390', name:'新能源汽车ETF'},
  {code:'sh513100', name:'纳指ETF国泰'},
];

function pearson(x, y) {
  if(x.length<10) return null;
  var n=x.length,mx=0,my=0;
  for(var i=0;i<n;i++){mx+=x[i];my+=y[i];}
  mx/=n;my/=n;
  var cov=0,sx=0,sy=0;
  for(var i=0;i<n;i++){
    var dx=x[i]-mx,dy=y[i]-my;
    cov+=dx*dy;sx+=dx*dx;sy+=dy*dy;
  }
  var d=Math.sqrt(sx*sy);
  return d===0?null:cov/d;
}

function returns(arr) {
  var r=[];
  for(var i=1;i<arr.length;i++) r.push((arr[i].close-arr[i-1].close)/arr[i-1].close);
  return r;
}

function fetch(code, name) {
  return new Promise(function(res) {
    // 腾讯日K
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param='+code+',day,,,120,qfq';
    https.get(url, {headers:{'Referer':'https://gu.qq.com'}}, function(r) {
      var d=''; r.on('data',function(s){d+=s;});
      r.on('end',function(){
        try {
          var txt = d.replace(/^[^=]+=/,'');
          var j = JSON.parse(txt);
          var arr = (j.data[code]&&j.data[code].qfqday)||(j.data[code]&&j.data[code].day)||[];
          var recs = arr.map(function(p){return {date:p[0],close:parseFloat(p[2])};});
          console.log((name||code).padEnd(14)+' '+recs.length+'条 末:'+(recs[recs.length-1]||{}).date+' 收:'+(recs[recs.length-1]||{}).close);
          res({name:name||code, recs:recs});
        } catch(e) {
          console.log((name||code)+' ERR:'+e.message.substring(0,50));
          res({name:name||code, recs:[]});
        }
      });
    }).on('error',function(){ console.log(name+' NET'); res({name:name||code,recs:[]}); });
  });
}

async function run() {
  var results=[];
  for(var i=0;i<codes.length;i++){
    var r=await fetch(codes[i].code, codes[i].name);
    results.push(r);
    await new Promise(function(cb){setTimeout(cb,400);});
  }

  var keys=results.filter(function(x){return x.recs.length>0;});
  if(keys.length<2){console.log('数据不足');return;}

  console.log('\n━━━ Pearson相关矩阵 ━━━');
  var h='               |';
  keys.forEach(function(k){h+=' '+(k.name||'').substring(0,6).padEnd(8)+'|';});
  console.log(h);
  console.log('-'.repeat(h.length));

  var resultMap={};
  keys.forEach(function(k){resultMap[k.name]=k;});

  for(var i=0;i<keys.length;i++){
    var row=(keys[i].name||'').substring(0,14).padEnd(14)+'|';
    for(var j=0;j<keys.length;j++){
      if(i===j){row+='  1.000  | ';}
      else {
        var r=pearson(returns(keys[i].recs),returns(keys[j].recs));
        if(r===null){row+='  N/A   | ';}
        else{var m=r>0.7?'🔴':r>0.5?'🟡':r>0.3?'🟢':'⚪';row+=m+' '+r.toFixed(3)+'| ';}
      }
    }
    console.log(row);
  }
  console.log('\n图例: 🔴>0.70  🟡0.50-0.70  🟢0.30-0.50  ⚪<0.30');

  // 510500重点分析
  var base=resultMap['中证500ETF南方'];
  if(base) {
    console.log('\n━━━ 510500(中证500ETF) vs 各持仓 ━━━');
    keys.forEach(function(k){
      if(k.name==='中证500ETF南方') return;
      var r=pearson(returns(base.recs),returns(k.recs));
      if(r!==null){
        var days=Math.min(base.recs.length,k.recs.length);
        var m=r>0.7?'🔴':r>0.5?'🟡':r>0.3?'🟢':'⚪';
        console.log('  '+k.name.padEnd(14)+' r='+r.toFixed(3)+'  '+m+' (共'+days+'日)');
      }
    });
  }
}
run().catch(function(e){console.error(e);});
