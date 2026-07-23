var fs=require('fs');
var d=JSON.parse(fs.readFileSync('D:/QClaw_Trading/data/index_history/sh000300.json','utf8'));
var r=(d.records||d).filter(function(x){return x.date>='2005-04-08'&&x.date<='2026-04-24';}).sort(function(a,b){return a.date.localeCompare(b.date);});
var closes=r.map(function(x){return x.close});
console.log('total closes:', closes.length, 'first:', closes[0], 'last:', closes[closes.length-1]);

var ma20=[];for(var i=0;i<closes.length;i++){if(i<19){ma20.push(null);}else{var s=0;for(var j=0;j<20;j++)s+=closes[i-j];ma20.push(s/20);}}

var ema12=closes.slice(),ema26=closes.slice();
for(var i=1;i<ema12.length;i++)ema12[i]=closes[i]*2/13+ema12[i-1]*11/13;
for(var i=1;i<ema26.length;i++)ema26[i]=closes[i]*2/27+ema26[i-1]*25/27;
var dif=ema12.map(function(v,i){return v-ema26[i];});
var dea=[dif[25]];for(var i=26;i<dif.length;i++)dea.push(dif[i]*2/10+dea[i-1]*8/10);

function maDir(ma,idx,lb){
  if(idx<lb)return'flat';
  var rec=ma.slice(Math.max(0,idx-lb+1),idx+1).filter(function(v){return v!==null;});
  if(rec.length<2)return'flat';
  return rec[rec.length-1]>rec[0]?'up':'dn';
}

// Count each condition
var condPrice=[0,0], condDif=[0,0], condDea=[0,0], condMaUp=[0,0];
for(var i=26;i<r.length;i++){
  var price=closes[i],ma=ma20[i];
  var macdUp=i>0&&dif[i-1]<dea[i-1]&&dif[i]>dea[i]&&dif[i]>0;
  var maUp=maDir(ma20,i,5)==='up';
  condPrice[price>ma?1:0]++;
  condDif[dif[i]>0?1:0]++;
  condDea[dif[i]>dea[i]?1:0]++;
  condMaUp[maUp?1:0]++;
}
console.log('price>ma: true='+condPrice[1]+' false='+condPrice[0]);
console.log('dif>0: true='+condDif[1]+' false='+condDif[0]);
console.log('dif>dea: true='+condDea[1]+' false='+condDea[0]);
console.log('maUp=true: '+condMaUp[1]+' false='+condMaUp[0]);

// Check crossUp
var crossUps=0;
for(var i=26;i<r.length;i++){
  if(i>0&&dif[i-1]<dea[i-1]&&dif[i]>dea[i])crossUps++;
}
console.log('MACD golden cross count:', crossUps);

// All 4 together
var all4=0;
for(var i=26;i<r.length;i++){
  var price=closes[i],ma=ma20[i];
  var crossUp=i>0&&dif[i-1]<dea[i-1]&&dif[i]>dea[i];
  var maUp=maDir(ma20,i,5)==='up';
  if(price>ma&&maUp&&crossUp&&dif[i]>0)all4++;
}
console.log('ALL 4 conditions (price>ma && maUp && crossUp && dif>0):', all4);

// If still 0, relax
if(all4===0){
  var priceAndMa=0,priceAndCross=0,priceAndDif=0;
  for(var i=26;i<r.length;i++){
    var price=closes[i],ma=ma20[i];
    var crossUp=i>0&&dif[i-1]<dea[i-1]&&dif[i]>dea[i];
    if(price>ma&&maUp&&crossUp)priceAndMa++;
    if(price>ma&&crossUp)priceAndCross++;
    if(price>ma&&dif[i]>0)priceAndDif++;
  }
  console.log('price>ma&&maUp&&crossUp:',priceAndMa);
  console.log('price>ma&&crossUp:',priceAndCross);
  console.log('price>ma&&dif>0:',priceAndDif);
  
  // Check specific early signals
  console.log('\nFirst 10 bars with ma20, dif, dea:');
  for(var i=26;i<Math.min(36,r.length);i++){
    var crossUp=i>0&&dif[i-1]<dea[i-1]&&dif[i]>dea[i];
    console.log('i='+i+' date='+r[i].date+' price='+closes[i].toFixed(2)+' ma20='+(ma20[i]?ma20[i].toFixed(2):'null')+' dif='+(dif[i]?dif[i].toFixed(3):'null')+' dea='+(dea[i]?dea[i].toFixed(3):'null')+' crossUp='+crossUp+' dif[i]>dea[i]='+(dif[i]>dea[i]));
  }
}
