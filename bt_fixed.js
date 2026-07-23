var fs=require('fs');
var d=JSON.parse(fs.readFileSync('D:/QClaw_Trading/data/index_history/sh000300.json','utf8'));
var r=(d.records||d).filter(function(x){return x.date>='2005-04-08'&&x.date<='2026-04-24';}).sort(function(a,b){return a.date.localeCompare(b.date);});
var closes=r.map(function(x){return x.close});
var ma20=[];for(var i=0;i<closes.length;i++){if(i<19){ma20.push(null);}else{var s=0;for(var j=0;j<20;j++)s+=closes[i-j];ma20.push(s/20);}}
var ema12=closes.slice(),ema26=closes.slice();
for(var i=1;i<ema12.length;i++)ema12[i]=closes[i]*2/13+ema12[i-1]*11/13;
for(var i=1;i<ema26.length;i++)ema26[i]=closes[i]*2/27+ema26[i-1]*25/27;
var dif=ema12.map(function(v,i){return v-ema26[i];});
var dea=[dif[25]];for(var i=26;i<dif.length;i++)dea.push(dif[i]*2/10+dea[i-1]*8/10);
function maDir(ma,idx,lb){if(idx<lb)return'flat';var rec=ma.slice(Math.max(0,idx-lb+1),idx+1).filter(function(v){return v!==null;});if(rec.length<2)return'flat';return rec[rec.length-1]>rec[0]?'up':'dn';}

var cash=100000,shares=0,state='out',trades=[];
for(var i=26;i<r.length;i++){
  var price=closes[i];
  if(state==='in'){
    var crossDn=i>0&&dif[i-1]>=dea[i-1]&&dif[i]<dea[i];
    if(price<ma20[i]||crossDn){
      cash+=shares*price;
      var entry=trades[trades.length-1]._e;
      trades.push({action:'SELL',date:r[i].date,ret:(price/entry-1)*100});
      shares=0;state='out';
    }
  }else{
    var macdUp=i>0&&dif[i-1]<dea[i-1]&&dif[i]>dea[i]&&dif[i]>0;
    var maUp=maDir(ma20,i,5)==='up';
    if(price>ma20[i]&&maUp&&macdUp){
      shares=Math.floor(cash/price/100)*100;
      cash-=shares*price;
      trades.push({action:'BUY',date:r[i].date,price:price,_e:price});
      state='in';
    }
  }
}
if(state==='in'){cash+=shares*closes[closes.length-1];trades.push({action:'SELL*',date:r[r.length-1].date});}
console.log('trades:',trades.length,'final cash:',cash.toFixed(0));
var wins=trades.filter(function(t){return t.ret>0;}).length;
var sells=trades.filter(function(t){return t.action&&t.action.startsWith('SELL');}).length;
console.log('wins:',wins,'/',sells,'winRate:',sells>0?(wins/sells*100).toFixed(0)+'%':'N/A');
console.log('bh ret:',(closes[closes.length-1]/closes[0]-1)*100,'%');
var years=(new Date(r[r.length-1].date)-new Date(r[0].date))/86400000/365.25;
var ann=(Math.pow(cash/100000,1/years)-1)*100;
console.log('annualized:',ann.toFixed(1)+'%','years:',years.toFixed(2));
var rets=[];for(var i=0;i<trades.length;i++){if(trades[i].ret!==undefined&&!isNaN(trades[i].ret))rets.push(trades[i].ret/100);}
if(rets.length>0)console.log('avg trade ret:',(rets.reduce(function(a,b){return a+b;},0)/rets.length*100).toFixed(1)+'%');
console.log('last 5 trades:',JSON.stringify(trades.slice(-5)));
