var fs=require('fs');
var d=JSON.parse(fs.readFileSync('D:/QClaw_Trading/data/index_history/sh000300.json','utf8'));
var r=(d.records||d).filter(function(x){return x.date>='2005-04-08';}).sort(function(a,b){return a.date.localeCompare(b.date);});
var closes=r.map(function(x){return x.close});

var ma20=[];
for(var i=0;i<closes.length;i++){
  if(i<19){ma20.push(null);}
  else{var s=0;for(var j=0;j<20;j++)s+=closes[i-j];ma20.push(s/20);}
}

var ema12=closes.slice(),ema26=closes.slice();
for(var i=1;i<ema12.length;i++)ema12[i]=closes[i]*2/13+ema12[i-1]*11/13;
for(var i=1;i<ema26.length;i++)ema26[i]=closes[i]*2/27+ema26[i-1]*25/27;
var dif=ema12.map(function(v,i){return v-ema26[i];});
var seed=0;for(var i=0;i<26;i++)seed+=dif[i];seed/=26;
var dea=new Array(dif.length).fill(null);
dea[25]=seed;
for(var i=26;i<dif.length;i++)dea[i]=dif[i]*2/10+dea[i-1]*8/10;

function maDir(ma,idx,lb){
  if(idx<lb||ma[idx]===null)return'flat';
  var rec=ma.slice(Math.max(0,idx-lb+1),idx+1).filter(function(v){return v!==null;});
  if(rec.length<2)return'flat';
  return rec[rec.length-1]>rec[0]?'up':'dn';
}

var cash=100000,shares=0,state='out',trades=[];
for(var i=26;i<r.length;i++){
  var price=closes[i];
  if(state==='in'){
    var macdDn=dif[i]<dea[i]&&dif[i-1]>=dea[i-1];
    if(price<ma20[i]||macdDn){
      cash+=shares*price;
      var entry=trades[trades.length-1]._e;
      trades.push({action:'SELL',date:r[i].date,price:price,ret:(price/entry-1)*100});
      shares=0;state='out';
    }
  }else{
    var macdUp=dif[i]>0&&dif[i]>dea[i]&&dif[i-1]<=dea[i-1];
    var maUp=maDir(ma20,i,5)==='up';
    if(price>ma20[i]&&maUp&&macdUp){
      shares=Math.floor(cash/price/100)*100;
      if(shares>0){cash-=shares*price;trades.push({action:'BUY',date:r[i].date,price:price,_e:price});state='in';}
    }
  }
}
if(state==='in'){
  cash+=shares*closes[closes.length-1];
  var entry=trades[trades.length-1]._e;
  trades.push({action:'SELL*',date:r[r.length-1].date,price:closes[closes.length-1],ret:(closes[closes.length-1]/entry-1)*100});
}

console.log('=== 沪深300 MA20+MACD 详细回测 ===');
console.log('bars:',r.length,' 初始100000 -> 最终'+cash.toFixed(0));
console.log('交易次数:',trades.length);
trades.forEach(function(t){console.log(' '+t.action+' '+t.date+' price='+t.price+' ret='+(t.ret!==undefined?t.ret.toFixed(2):'--')+'%');});
var sells=trades.filter(function(t){return t.action&&t.action.startsWith('SELL');});
var wins=trades.filter(function(t){return t.ret>0;}).length;
console.log('胜率: '+wins+'/'+sells.length+'='+(sells.length>0?(wins/sells.length*100).toFixed(0)+'%':'N/A'));
var years=(new Date(r[r.length-1].date)-new Date(r[0].date))/86400000/365.25;
console.log('年化: '+((Math.pow(cash/100000,1/years)-1)*100).toFixed(1)+'%');
console.log('买入持有年化: '+((Math.pow(closes[closes.length-1]/closes[0],1/years)-1)*100).toFixed(1)+'%');
