var fs = require('fs');
var d = JSON.parse(fs.readFileSync('D:/QClaw_Trading/data/index_history/sh000300.json','utf8'));
var r = (d.records||d).sort(function(a,b){return a.date.localeCompare(b.date);});
var closes = r.map(function(x){return x.close;});
console.log('总bar数:', r.length, '价格范围:', Math.min(...closes), '~', Math.max(...closes));

// EMA12
var ema12 = [closes[0]];
for(var i=1;i<closes.length;i++) ema12[i] = closes[i]*2/13 + ema12[i-1]*11/13;
// EMA26
var ema26 = [closes[0]];
for(var i=1;i<closes.length;i++) ema26[i] = closes[i]*2/27 + ema26[i-1]*25/27;
// DIF
var dif = ema12.map(function(v,i){return v-ema26[i];});
// DEA种子法
var dea = new Array(dif.length);
dea[25] = dif[25]; // 种子 = dif[25]
for(var i=26;i<dif.length;i++) dea[i] = dif[i]*2/10 + dea[i-1]*8/10;

console.log('\n=== EMA12 vs EMA26 ===');
for(var i=0;i<5;i++) console.log('i='+i+' close='+closes[i].toFixed(2)+' ema12='+ema12[i].toFixed(2)+' ema26='+ema26[i].toFixed(2)+' dif='+dif[i].toFixed(3));
console.log('...');
for(var i=24;i<30;i++) console.log('i='+i+' close='+closes[i].toFixed(2)+' ema12='+ema12[i].toFixed(2)+' ema26='+ema26[i].toFixed(2)+' dif='+dif[i].toFixed(3)+' dea='+(dea[i]!==undefined?dea[i].toFixed(3):'undef'));

console.log('\n=== DIF vs DEA 样本 ===');
[100, 500, 1000, 2000, 3000, 4000, 5000, 5100].forEach(function(i){
  if(i<dif.length) console.log('i='+i+' date='+r[i].date+' dif='+dif[i].toFixed(3)+' dea='+(dea[i]!==undefined?dea[i].toFixed(3):'undef')+' dif>dea='+(dif[i]>dea[i]));
});

console.log('\n=== DIF>DEA统计 ===');
var cnt=0;for(var i=26;i<dif.length;i++) if(dif[i]>dea[i]) cnt++;
console.log('DIF>DEA次数:', cnt, '/', dif.length-26);
var gc=0;for(var i=26;i<dif.length-1;i++) if(dif[i]<=dea[i]&&dif[i+1]>dea[i+1]) gc++;
console.log('金叉(DIF从<=DEA变>DIF[DEA])次数:', gc);
var gc2=0;for(var i=26;i<dif.length-1;i++) if(dif[i]<dea[i]&&dif[i+1]>dea[i+1]) gc2++;
console.log('金叉(DIF从<DEA变>DEA)次数:', gc2);

// 正确金叉判断
var gc3=0,lastDea;for(var i=26;i<dif.length-1;i++){
  if(dea[i]!==undefined&&dea[i+1]!==undefined&&dea[i]!==null&&dea[i+1]!==null){
    if(dif[i]<=dea[i]&&dif[i+1]>dea[i+1]) gc3++;
  }
}
console.log('正确金叉(非null DEA):', gc3);

// 检查dea从哪开始有效
var deaValid=0;for(var i=26;i<dif.length;i++) if(!isNaN(dea[i])) deaValid++;
console.log('dea有效值数量:', deaValid, '/', dif.length-26);

// 尝试另一种DEA初始化：不用种子法，用SMA作为种子
var dea2 = new Array(dif.length);
var sma26 = 0; for(var i=0;i<26;i++) sma26 += dif[i]; sma26 /= 26; // 前26日简单均值
dea2[25] = sma26;
for(var i=26;i<dif.length;i++) dea2[i] = dif[i]*2/10 + dea2[i-1]*8/10;
var cnt2=0; for(var i=26;i<dif.length;i++) if(dif[i]>dea2[i]) cnt2++;
var gc4=0; for(var i=26;i<dif.length-1;i++) if(dea2[i]!==undefined&&dea2[i+1]!==undefined&&dif[i]<=dea2[i]&&dif[i+1]>dea2[i+1]) gc4++;
console.log('\n=== 改用SMA26作DEA种子 ===');
console.log('DIF>DEA2次数:', cnt2);
console.log('金叉次数:', gc4);
console.log('样本: i=100 dif='+dif[100].toFixed(3)+' dea2='+dea2[100].toFixed(3));
console.log('样本: i=500 dif='+dif[500].toFixed(3)+' dea2='+dea2[500].toFixed(3));
console.log('样本: i=2000 dif='+dif[2000].toFixed(3)+' dea2[2000]='+(dea2[2000]?dea2[2000].toFixed(3):'undef'));
