// 快速测试：跑一只ETF验证 v3.4 脚本无语法错误
var https = require('https');
var path  = require('path');
var fs    = require('fs');

// ── 直接复制 scan_global_etf.js 的关键函数 ──
function SMA(prices, n) {
  var out = new Array(prices.length).fill(null);
  for (var i = n-1; i < prices.length; i++) {
    var s = 0; for (var j = i-n+1; j <= i; j++) s += prices[j];
    out[i] = s / n;
  }
  return out;
}
function EMA(prices, n) {
  var k = 2/(n+1), out = new Array(prices.length).fill(null);
  var seed = 0; for (var i = 0; i < n; i++) seed += prices[i];
  out[n-1] = seed / n;
  for (var i = n; i < prices.length; i++) out[i] = prices[i]*k + out[i-1]*(1-k);
  return out;
}
function MACD(prices, f, s, sig) {
  f=f||12;s=s||26;sig=sig||9;
  var ef=EMA(prices,f),es=EMA(prices,s);
  var dif=new Array(prices.length).fill(null);
  for(var i=s-1;i<prices.length;i++) dif[i]=ef[i]-es[i];
  var sk=2/(sig+1),se=new Array(prices.length).fill(null);
  se[s-1]=dif[s-1];
  for(var i=s;i<dif.length;i++) se[i]=dif[i]*sk+se[i-1]*(1-sk);
  var hist=dif.map(function(v,i){return v===null?null:v-se[i];});
  return{dif:dif,sig:se,hist:hist};
}
function pctReturn(C,n){
  if(n>0&&C.length>n)return(C[C.length-1]-C[C.length-1-n])/C[C.length-1-n]*100;
  return null;
}
// v3.4 修复版 Pearson（基于日收益率）
function pearsonCorr(C1,C2){
  function toReturns(ps){var r=[];for(var i=1;i<ps.length;i++){if(ps[i]>0&&ps[i-1]>0)r.push((ps[i]-ps[i-1])/ps[i-1]);}return r;}
  var R1=toReturns(C1),R2=toReturns(C2);
  var n=Math.min(R1.length,R2.length,60);
  var s1=R1.length-n,s2=R2.length-n;
  var sumX=0,sumY=0,sumXY=0,sumX2=0,sumY2=0;
  for(var i=0;i<n;i++){var x=R1[s1+i],y=R2[s2+i];sumX+=x;sumY+=y;sumXY+=x*y;sumX2+=x*x;sumY2+=y*y;}
  var num=n*sumXY-sumX*sumY,den=Math.sqrt((n*sumX2-sumX*sumX)*(n*sumY2-sumY*sumY));
  return den===0?0:num/den;
}
function calcStarScore(data,bmPct20){
  if(data.length<60)return{stars:1,score:0};
  var C=data.map(function(d){return d.close;}),V=data.map(function(d){return d.vol;});
  var ma20=SMA(C,20),ma50=SMA(C,50),ma200=SMA(C,200),macd=MACD(C,12,26,9);
  var i=data.length-1,i1=data.length-2;
  var price=C[i],vol=V[i],volAvg=V.slice(i-19,i+1).reduce(function(a,b){return a+b;},0)/20;
  var ma20c=ma20[i],ma20p1=ma20[i1],ma50c=ma50[i],ma50p1=ma50[i1],ma200c=ma200[i];
  var d=macd.dif[i],dP1=macd.dif[i1],s=macd.sig[i],sP1=macd.sig[i1],h=macd.hist[i],hP1=macd.hist[i1];
  var aboveMa20=price>ma20c,ma20Up=ma20c>=ma20p1,ma20Above50=ma50c?ma20c>ma50c:false;
  var ma50Above200=ma200c?ma50c>ma200c:false,macdAboveZero=d>0&&s>0;
  var goldX=dP1<=sP1&&d>s;
  var histUp=h>0&&h>hP1;
  var pct5=pctReturn(C,5),pct20=pctReturn(C,20);
  var bm=bmPct20!==null?bmPct20:0;
  var relStr20=pct20!==null?pct20-bm:0;
  var score=0;
  if(aboveMa20)score+=1;
  if(ma20Above50)score+=1;
  if(ma20Above50&&ma50Above200)score+=2;
  if(ma20Up)score+=1;
  if(macdAboveZero)score+=1;
  if(goldX&&macdAboveZero)score+=2;else if(goldX)score+=1;
  if(histUp)score+=1;
  if(relStr20>0)score+=2;
  if(vol>volAvg*1.5)score+=1;
  var stars=1;if(score>=11)stars=5;else if(score>=9)stars=4;else if(score>=6)stars=3;else if(score>=4)stars=2;
  // v3.4: 只用MA20跌破作为卖出，不依赖死叉/绿柱
  var signal='n',tag='';
  if(!aboveMa20){signal='n';tag='跌破MA20(等待)';}
  else if(goldX&&macdAboveZero){signal='B';tag='零轴上金叉(买入)';}
  else if(goldX){signal='B';tag='MACD金叉(买入)';}
  else if(macdAboveZero&&h>0){signal='H';tag='零轴上方持股';}
  else{signal='H';tag='趋势持股';}
  return{stars:stars,score:score,signal:signal,tag:tag,pct20:pct20,aboveMa20:aboveMa20,goldX:goldX,macdAboveZero:macdAboveZero,corrData:C.slice(-60)};
}

function fetchKline(code){
  return new Promise(function(res){
    var url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param='+code+',day,,,120,qfq';
    https.get(url,{headers:{'Referer':'https://gu.qq.com'}},function(r){
      var d='';r.on('data',function(s){d+=s;});
      r.on('end',function(){
        try{
          var j=JSON.parse(d.replace(/^[^=]+=/,''));
          var arr=(j.data[code]&&j.data[code].qfqday)||(j.data[code]&&j.data[code].day)||[];
          res(arr.map(function(p){return{date:p[0],close:parseFloat(p[2]),vol:parseFloat(p[5])};}));
        }catch(e){res([]);}
      });
    }).on('error',function(){res([]);});
  });
}

// ── 测试用例 ──
async function test(){
  console.log('=== v3.4 扫描函数测试 ===\n');
  // 创业板指基准
  var idx=await fetchKline('sz399006');
  var bmPct20=pctReturn(idx.map(function(d){return d.close;}),20);
  console.log('创业板指基准 pct20:',bmPct20!==null?bmPct20.toFixed(2)+'%':'无数据','\n');

  // 测试各ETF
  var tests=[
    {code:'sz159681',name:'创业板50ETF'},
    {code:'sh512770',name:'战略新兴ETF'},
    {code:'sh512220',name:'TMTETF'},
    {code:'sh516390',name:'新能源汽车ETF'},
    {code:'sh513100',name:'纳指ETF'},
    {code:'sh510500',name:'中证500ETF'},
  ];

  var results=[];
  for(var t of tests){
    var k=await fetchKline(t.code);
    await new Promise(function(cb){setTimeout(cb,300);});
    if(k.length<30){console.log(t.name+': K线不足');continue;}
    var r=calcStarScore(k,bmPct20);
    results.push({name:t.name,code:t.code,...r,klen:k.length});
    console.log('  '+(r.signal==='B'?'BUY✅':r.signal==='H'?'HOLD ':'WAIT❌')+' '+t.name.padEnd(12)+' ⭐'.repeat(r.stars)+'('+r.score+'分)  MA20'+(r.aboveMa20?'↗':'↘')+'  '+r.tag+'  20日'+r.pct20.toFixed(1)+'%  '+k.length+'条');
  }

  // 相关性矩阵（收益率版）
  console.log('\n=== 相关性矩阵（基于日收益率，v3.4）===');
  var fmt=function(s){return s.padEnd(10);};
  var names=results.map(function(r){return r.name;});
  console.log(fmt('') + '|' + names.map(function(n){return fmt(n.substring(0,7))+'|';}).join(''));
  console.log('-'.repeat(names.length*12+16));
  for(var i=0;i<results.length;i++){
    var row=fmt(results[i].name.substring(0,8))+'|';
    for(var j=0;j<results.length;j++){
      if(i===j){row+=fmt(' 1.000 ')+'| ';}else{
        var r=pearsonCorr(results[i].corrData,results[j].corrData);
        var badge=r>0.7?'🔴':r>0.5?'🟡':r>0.3?'🟢':'⚪';
        row+=fmt(badge+r.toFixed(2))+'| ';
      }
    }
    console.log(row);
  }
}
test().catch(function(e){console.error(e);});
