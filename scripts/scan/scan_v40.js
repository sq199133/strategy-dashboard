// scan_v40.js - ETF信号扫描 v4.0
// 优化：使用curl获取实时数据 + 本地历史数据 + 改进去度采样
// 策略：MA20+MACD v3.9 + 夏普比率优化(目标>1)
// 用法: node scan_v40.js
'use strict';
var execSync = require('child_process').execSync;
var fs = require('fs');
var path = require('path');

var POOL_FILE = path.join(__dirname, 'etf_pool.json');
var HIST_DIR = 'D:\\QClaw_Trading\\data\\history';
var ALL_ETFS = JSON.parse(fs.readFileSync(POOL_FILE, 'utf8'));
console.log('共加载 ' + ALL_ETFS.length + ' 只ETF (v5.1)\n');

// ─── curl获取实时数据 ───
function curl(url) {
  try {
    return execSync(
      'curl.exe -s --max-time 8 -H "Referer: https://gu.qq.com/" --url ' + JSON.stringify(url),
      { encoding: 'utf8', timeout: 10000, windowsHide: true }
    );
  } catch(e) { return null; }
}

// 获取单只ETF日K(最新N条)
function fetchKline(sym, maxBars) {
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + sym + ',day,,,' + maxBars + ',qfq';
  var raw = curl(url);
  if (!raw) return [];
  try {
    var j = JSON.parse(raw);
    var d = j.data && j.data[sym];
    return (d && (d.qfqday || d.day)) || [];
  } catch(e) { return []; }
}

function convert(arr) {
  return arr.map(function(p) {
    return { date: p[0], open: +p[1], close: +p[2], high: +p[3], low: +p[4], vol: parseInt(p[5]) || 0, chg: +p[7] || 0 };
  });
}

// ─── 技术指标 ───
function SMA(prices, n) {
  var out = new Array(prices.length).fill(null);
  for (var i = n-1; i < prices.length; i++) {
    var s = 0;
    for (var j = i-n+1; j <= i; j++) s += prices[j];
    out[i] = s / n;
  }
  return out;
}

function EMA(prices, n) {
  var k = 2/(n+1);
  var ef = [];
  ef[n-1] = prices.slice(0,n).reduce(function(a,b){return a+b;},0)/n;
  for (var i=n; i<prices.length; i++) ef[i] = prices[i]*k + ef[i-1]*(1-k);
  return new Array(n-1).fill(null).concat(ef.slice(n-1));
}

function MACD(prices, f, s, sig) {
  f = f||12; s=s||26; sig=sig||9;
  var ef=EMA(prices,f), es=EMA(prices,s);
  var dif=prices.map(function(v,i){ return (ef[i]!==null&&es[i]!==null)?ef[i]-es[i]:null; });
  var sk=2/(sig+1), se=[];
  for (var i=s-1; i<dif.length; i++) {
    if (dif[i]!==null) se[i]=dif[i];
  }
  for (var i=s; i<dif.length; i++) {
    se[i]=(dif[i]!==null)?dif[i]*sk+se[i-1]*(1-sk):null;
  }
  var hist=dif.map(function(v,i){ return (v!==null&&se[i]!==null)?v-se[i]:null; });
  return { dif:dif, sig:se, hist:hist };
}

function pctReturn(prices, n) {
  if (n<1 || prices.length<n+1) return null;
  var end=prices.length-1, start=end-n;
  return prices[start]>0?(prices[end]-prices[start])/prices[start]*100:null;
}

// ─── 相关性(120日收益率Pearson) ───
function pearsonCorr(prices1, prices2) {
  function toReturns(arr) {
    var r=[];
    for (var i=1; i<arr.length; i++) {
      if (arr[i]>0 && arr[i-1]>0) r.push((arr[i]-arr[i-1])/arr[i-1]);
    }
    return r;
  }
  var r1=toReturns(prices1), r2=toReturns(prices2);
  var n=Math.min(r1.length, r2.length, 120);
  if (n<10) return 0;
  var s1=r1.length-n, s2=r2.length-n;
  var sumX=0,sumY=0,sumXY=0,sumX2=0,sumY2=0;
  for (var i=0;i<n;i++) {
    var x=r1[s1+i], y=r2[s2+i];
    sumX+=x; sumY+=y; sumXY+=x*y; sumX2+=x*x; sumY2+=y*y;
  }
  var den=Math.sqrt((n*sumX2-sumX*sumX)*(n*sumY2-sumY*sumY));
  return den===0?0:(n*sumXY-sumX*sumY)/den;
}

// ─── 市场分类(v5.1) ───
function etfMarket(etf) {
  var nm = (etf.name||'') + (etf.index||'') + (etf.category||'');
  if (etf.category==='商品/资源' || /黄金|白银|石油|大宗|原油|能源|商品/.test(nm)) return '商品';
  if (etf.category==='跨境QDII') {
    if (/港股|恒生|H股|港中小|恒生科技|港股通|中概/.test(nm)) return '港股';
    if (/纳指|纳斯达克|NDX|标普|SPX|道琼斯|美股/.test(nm)) return '美股';
    return '其他';
  }
  return 'A股';
}

// ─── 追高过滤(calcChaseFilter) ───
function calcChase(prices) {
  if (prices.length<5) return { redLine:false, yellowCount:0, bias20:null, pct3d:null, pct5d:null, consecUp:0 };
  var i=prices.length-1;
  var ma20=SMA(prices,20);
  var ma=ma20[i];
  var bias20=ma>0?(prices[i]-ma)/ma*100:null;
  var pct3d=prices[i-3]>0?(prices[i]-prices[i-3])/prices[i-3]*100:null;
  var pct5d=prices[i-5]>0?(prices[i]-prices[i-5])/prices[i-5]*100:null;
  var consecUp=0;
  for (var j=i;j>0;j--) { if (prices[j]>prices[j-1]) consecUp++; else break; }
  var yc=0, rl=false;
  var det=[];
  if (bias20!==null && bias20>5 && bias20<=8)  { yc++; det.push('Y:BIAS='+bias20.toFixed(1)+'%'); }
  if (pct3d!==null && pct3d>5 && pct3d<=10)     { yc++; det.push('Y:3d='+pct3d.toFixed(1)+'%'); }
  if (pct5d!==null && pct5d>10 && pct5d<=15)   { yc++; det.push('Y:5d='+pct5d.toFixed(1)+'%'); }
  if (consecUp>=5 && consecUp<=7)                 { yc++; det.push('Y:连涨'+consecUp+'天'); }
  if (bias20!==null && bias20>8)                  { rl=true; det.push('R:BIAS='+bias20.toFixed(1)+'%'); }
  if (pct3d!==null && pct3d>10)                 { rl=true; det.push('R:3d='+pct3d.toFixed(1)+'%'); }
  if (pct5d!==null && pct5d>15)                 { rl=true; det.push('R:5d='+pct5d.toFixed(1)+'%'); }
  if (consecUp>=8)                               { rl=true; det.push('R:连涨'+consecUp+'天>=8'); }
  if (yc>=3)                                     { rl=true; det.push('R:yCount='+yc); }
  return { redLine:rl, yellowCount:yc, bias20:bias20, pct3d:pct3d, pct5d:pct5d, consecUp:consecUp, details:det };
}

// ─── v4.0核心评分(含夏普相关因子) ───
function calcStar(data, etf, bm20, bm5) {
  var C=data.map(function(d){return d.close;});
  var V=data.map(function(d){return d.vol;});
  if (C.length<60) return null;
  var i=C.length-1, i1=i-1;
  var ma20=SMA(C,20), ma50=SMA(C,50), ma200=SMA(C,200);
  var macd=MACD(C,12,26,9);
  var price=C[i], ma20c=ma20[i], ma50c=ma50[i];
  if (ma20c===null) return null;
  var ma20p1=ma20[i1]||ma20c;
  var ma50p1=ma50[i1]||ma50c;
  var d=macd.dif[i], s=macd.sig[i], h=macd.hist[i];
  var dP1=macd.dif[i1], sP1=macd.sig[i1];
  var aboveMa20=price>ma20c;
  var ma20Up=ma20c>ma20p1;
  var ma20Above50=ma50c!==null && ma20c>ma50c;
  var ma50Above200=ma200[i]!==null && ma50c>ma200[i];
  var macdAboveZero=d>0 && s>0;
  var goldX=dP1!==null && sP1!==null && dP1<=sP1 && d>s;
  var histRed=h>0;
  var pct5=pctReturn(C,5), pct20=pctReturn(C,20);
  var mkt=etfMarket(etf);
  var isAbsMom=(mkt==='商品'||mkt==='其他');
  var bmPos=isAbsMom || (bm20>0);
  var relStr20=isAbsMom?0:(pct20-bm20);
  var relStr5=isAbsMom?0:(pct5-bm5);
  var volAvg=V.slice(i-19,i+1).reduce(function(a,b){return a+b;},0)/20;
  
  // 追高过滤
  var chase=calcChase(C);
  if (chase.redLine) return null; // 红线禁买

  var score=0;
  // 趋势(0-5)
  if (aboveMa20) score+=1;
  if (ma20Above50) score+=1;
  if (ma20Above50 && ma50Above200) score+=2;
  if (ma20Up) score+=1;
  // 动量(0-4)
  if (goldX && macdAboveZero) score+=3;
  else if (goldX) score+=1;
  if (histRed) score+=1;
  // 相对强弱(0-3)
  if (isAbsMom) {
    if (pct20>0) score+=2;
    if (pct5>0) score+=1;
  } else if (mkt==='美股') {
    if (relStr20>=0) score+=2;
    if (relStr5>=0) score+=1;
  } else {
    if (relStr20>0) score+=2;
    if (relStr5>0) score+=1;
  }
  // 成交量(0-1)
  if (V[i]>volAvg*1.5) score+=1;
  // 夏普优化加成：分市场强势+BIAS20适中
  if (!chase.redLine) {
    score=Math.max(0, score-chase.yellowCount);
  }
  
  var stars=score>=10?5:score>=8?4:score>=6?3:score>=4?2:1;
  var signal;
  if (!aboveMa20) signal='WAIT';
  else if (!ma20Up) signal='HOLD';
  else if (goldX && macdAboveZero && bmPos) signal='BUY';
  else if (goldX && bmPos) signal='BUY';
  else if (macdAboveZero && histRed && bmPos) signal='BUY';
  else if (macdAboveZero && histRed) signal='HOLD';
  else signal='HOLD';
  
  // 黄金价差预警
  var gwarn='';
  if (/黄金/.test(etf.name) && aboveMa20) {
    var gap=(price-ma20c)/ma20c*100;
    if (gap<0.5) gwarn='SELL_NOW';
    else if (gap<1) gwarn='WARN';
  }
  
  return {
    etf:etf, date:data[i].date, price:price, ma20:ma20c,
    ma20Dir:ma20Up?'↑':'↓', ma50:ma50c,
    zone:macdAboveZero?'零轴上':'零轴下',
    pct5:pct5, pct20:pct20,
    relStr20:isAbsMom?(pct20>0?'+':'-') : (relStr20>0?'+'+relStr20.toFixed(1)+'%':relStr20.toFixed(1)+'%'),
    score:score, stars:stars, signal:signal,
    mkt:mkt, bmName:bmPos?'强':'弱',
    sellSignal:!aboveMa20,
    chase:chase, gwarn:gwarn,
    corrData:C.slice(-120)
  };
}

// ─── 相关性过滤 ───
function filterCorr(buys) {
  if (buys.length<=1) return buys;
  buys.sort(function(a,b){ if(b.stars!==a.stars)return b.stars-a.stars; return b.score-a.score; });
  var sel=[];
  buys.forEach(function(c) {
    var maxC=0;
    sel.forEach(function(s){ var r=pearsonCorr(s.corrData,c.corrData); if(r>maxC) maxC=r; });
    c.maxCorr=maxC;
    if (maxC<=0.70) sel.push(c);
  });
  buys.forEach(function(b){ b.filtered=!sel.some(function(s){return s.etf.code===b.etf.code;}); });
  return buys;
}

// ─── 输出 ───
function pad(s,n) { s=String(s||'--'); while(s.length<n) s+=' '; return s; }
function fmt(n,d) { return n===null?'--':n.toFixed(d)+'%'; }

function printRow(r) {
  var chase=r.chase.redLine?' 🔴':(r.chase.yellowCount>0?' 🟡'+r.chase.yellowCount:'');
  var gw=r.gwarn?' ⚠️'+r.gwarn:'';
  var corr=r.maxCorr>0?' ↔'+r.maxCorr.toFixed(2):'';
  console.log(
    '  '+pad(r.etf.category,10)+pad(r.etf.name,16)+pad(r.etf.code,8)+
    pad('⭐'.repeat(r.stars),5)+pad(r.price.toFixed(3),8)+
    pad(r.ma20.toFixed(3),7)+pad(r.ma20Dir,2)+
    pad(r.zone,5)+pad(fmt(r.pct20,1),9)+
    pad('rel'+r.relStr20,11)+'  '+r.signal+chase+gw+corr
  );
}

// ─── 主程序 ───
function sleep(ms,cb){ setTimeout(cb,ms); }

var results=[];
var done=0;

console.log('══════════════════════════════════════════════════');
console.log('  ETF信号扫描 v4.0 | '+ALL_ETFS.length+'只 | MA20+MACD+追高过滤+夏普优化');
console.log('══════════════════════════════════════════════════\n');

function processNext() {
  if (done>=ALL_ETFS.length) {
    // ── 输出结果 ──
    var buys=results.filter(function(r){return r && r.signal==='BUY';});
    var holds=results.filter(function(r){return r && r.signal==='HOLD';});
    var waits=results.filter(function(r){return r && (r.signal==='WAIT' || r===null || r.signal===undefined);});
    var reds=results.filter(function(r){return r && r.signal===null;});
    console.log('\n══════════════════════════════════════════════════');
    console.log('  信号统计  |  BUY='+buys.length+'  HOLD='+holds.length+'  WAIT='+waits.length+'  过滤='+reds.length);
    console.log('══════════════════════════════════════════════════\n');
    var filtered=filterCorr(buys);
    var passed=filtered.filter(function(r){return !r.filtered;});
    var rejected=filtered.filter(function(r){return r.filtered;});
    if (passed.length>0) {
      console.log('>> BUY ('+passed.length+'只，已通过相关性)');
      console.log('  '+pad('类别',10)+pad('名称',16)+pad('代码',8)+pad('星级',5)+pad('收盘',8)+pad('MA20',7)+pad('Dir',2)+pad('Zone',5)+pad('20日%',9)+pad('相对强弱',11)+'  信号');
      passed.forEach(printRow);
      console.log('');
    }
    if (rejected.length>0) {
      console.log('>> BUY-FILTERED ('+rejected.length+'只)');
      rejected.forEach(printRow);
      console.log('');
    }
    if (holds.length>0) {
      holds.sort(function(a,b){ if(b.stars!==a.stars)return b.stars-a.stars; return b.score-a.score; });
      console.log('>> HOLD ('+holds.length+'只)');
      console.log('  '+pad('类别',10)+pad('名称',16)+pad('代码',8)+pad('星级',5)+pad('收盘',8)+pad('MA20',7)+pad('Dir',2)+pad('Zone',5)+pad('20日%',9)+pad('相对强弱',11)+'  信号');
      holds.slice(0,20).forEach(printRow);
      if (holds.length>20) console.log('  ... 还有'+(holds.length-20)+'只HOLD省略');
      console.log('');
    }
    return;
  }
  
  var etf=ALL_ETFS[done];
  var prefix=etf.market==='SZ'?'sz':'sh';
  var sym=prefix+etf.code;
  process.stdout.write('['+(done+1)+'/'+ALL_ETFS.length+'] '+etf.name+'('+sym+')... ');
  
  var raw=fetchKline(sym, 200);
  if (!raw.length) {
    console.log('FAIL(network)');
    results.push(null);
    done++;
    sleep(100, processNext);
    return;
  }
  var data=convert(raw);
  data.sort(function(a,b){return b.date.localeCompare(a.date);});
  if (data.length<60) {
    console.log('FAIL(data<60bars)');
    results.push(null);
    done++;
    sleep(100, processNext);
    return;
  }
  // 基准(简化：A股用沪深300, 港股用恒生, 美股用标普500)
  var mkt=etfMarket(etf);
  var bmSym='sh000300';
  if (mkt==='港股') bmSym='hkHSI';
  if (mkt==='美股') bmSym='sz513500';
  var bmRaw=fetchKline(bmSym, 100);
  var bm20=0, bm5=0;
  if (bmRaw.length>=60) {
    var bmC=convert(bmRaw).sort(function(a,b){return b.date.localeCompare(a.date);}).map(function(d){return d.close;});
    bm20=pctReturn(bmC,20)||0;
    bm5=pctReturn(bmC,5)||0;
  }
  
  var r=calcStar(data, etf, bm20, bm5);
  if (r) {
    var sig=r.signal;
    console.log(sig+' ⭐'+r.stars+' MA20'+r.ma20Dir+' pct20:'+fmt(r.pct20,1)+' rel:'+r.relStr20+' '+r.zone+(r.chase.redLine?' 🔴':'')+(r.gwarn?' ⚠️:' )+(r.yellowCount>0?' y'+r.yellowCount:''));
  } else {
    console.log('FILTERED (红线/不足数据)');
  }
  results.push(r);
  done++;
  sleep(120, processNext);
}

processNext();
