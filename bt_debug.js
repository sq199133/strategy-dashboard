var fs=require('fs');
var d=JSON.parse(fs.readFileSync('D:/QClaw_Trading/data/index_history/sh000300.json','utf8'));
var r=(d.records||d).filter(function(x){return x.date>='2005-04-08'&&x.date<='2026-04-24';}).sort(function(a,b){return a.date.localeCompare(b.date);});
console.log('bars:',r.length,'first close:',r[0].close,'last close:',r[r.length-1].close);
var closes=r.map(function(x){return x.close;});

var ma20=[];
for(var i=0;i<closes.length;i++){if(i<19){ma20.push(null);}else{var s=0;for(var j=0;j<20;j++)s+=closes[i-j];ma20.push(s/20);}}

var ema12=closes.slice(),ema26=closes.slice();
for(var i=1;i<ema12.length;i++)ema12[i]=closes[i]*2/13+ema12[i-1]*11/13;
for(var i=1;i<ema26.length;i++)ema26[i]=closes[i]*2/27+ema26[i-1]*25/27;
var dif=ema12.map(function(v,i){return v-ema26[i];});
var dea=[dif[25]];for(var i=26;i<dif.length;i++)dea.push(dif[i]*2/10+dea[i-1]*8/10);

var cash=100000,shares=0,state='out',equity=[],trades=[];
for(var i=26;i<r.length;i++){
  var price=closes[i];
  var nav=cash+shares*price;
  equity.push({nav:nav,date:r[i].date});
  if(state==='in'){
    if(price<ma20[i]||(dif[i-1]>=dea[i-1]&&dif[i]<dea[i])){
      cash+=shares*price;
      trades.push({action:'SELL',date:r[i].date,price:price,ret:(price/trades[trades.length-1]._entry-1)*100});
      shares=0;state='out';
    }
  }else{
    var maUp=true;
    if(ma20[i-1]!==null&&ma20[i]!==null&&ma20[i]<=ma20[i-1])maUp=false;
    if(price>ma20[i]&&dif[i]>0&&dif[i-1]<dea[i-1]&&dif[i]>dea[i]&&maUp){
      shares=Math.floor(cash/price/100)*100;
      cash-=shares*price;
      trades.push({action:'BUY',date:r[i].date,price:price,_entry:price});
      state='in';
    }
  }
}
if(state==='in'){cash+=shares*closes[closes.length-1];trades.push({action:'SELL*',date:r[r.length-1].date});}
console.log('trades:',trades.length,'cash final:',cash.toFixed(0),'shares final:',shares);
console.log('first 3 trades:',JSON.stringify(trades.slice(0,3)));
console.log('last 3 trades:',JSON.stringify(trades.slice(-3)));
console.log('equity[0]:',equity[0].nav,'equity[-1]:',equity[equity.length-1].nav);
console.log('bh ret:',(closes[closes.length-1]/closes[0]-1)*100,'%');
console.log('years:',(new Date(r[r.length-1].date)-new Date(r[0].date))/86400000/365.25);
