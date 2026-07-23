// Check star ratings for holdings using same API as scan_global_etf.js
var https = require('https');

var holdings = [
  { code: '159681', name: '创业板50ETF鹏华', market: 'SZ' },
  { code: '512770', name: '战略新兴ETF华夏', market: 'SH' },
  { code: '512220', name: 'TMTETF景顺', market: 'SH' },
  { code: '516390', name: '新能源汽车ETF', market: 'SH' },
  { code: '513100', name: '纳指ETF国泰', market: 'SH' }
];

function txSecid(code, market) {
  return market === 'SZ' ? 'sz' + code : 'sh' + code;
}

function fetchKline(code, market) {
  return new Promise(function(resolve) {
    var secid = txSecid(code, market);
    var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,150,qfq';
    https.get(url, function(res) {
      var data = '';
      res.on('data', function(chunk) { data += chunk; });
      res.on('end', function() {
        try {
          var obj = JSON.parse(data);
          var arr = obj.data && obj.data[secid]
            ? (obj.data[secid].qfqday || obj.data[secid].day || [])
            : [];
          if (arr.length < 30) {
            resolve({ code: code, name: holdings.find(function(h){ return h.code===code; }).name, error: 'no data (' + arr.length + ' bars)' });
            return;
          }
          
          var closes = arr.map(function(d) { return parseFloat(d[2]); });
          var dates = arr.map(function(d) { return d[0]; });
          
          // MA20
          var ma20 = [];
          for (var i = 0; i < closes.length; i++) {
            if (i < 19) { ma20.push(null); continue; }
            var sum = 0;
            for (var j = i - 19; j <= i; j++) sum += closes[j];
            ma20.push(sum / 20);
          }
          
          // MACD (12,26,9)
          var ema12 = [closes[0]];
          var ema26 = [closes[0]];
          for (var i = 1; i < closes.length; i++) {
            ema12.push(ema12[i-1] * 11/13 + closes[i] * 2/13);
            ema26.push(ema26[i-1] * 25/27 + closes[i] * 2/27);
          }
          var dif = ema12.map(function(v, i) { return v - ema26[i]; });
          var dea = [dif[0]];
          for (var i = 1; i < dif.length; i++) {
            dea.push(dea[i-1] * 8/10 + dif[i] * 2/10);
          }
          var macdBar = dif.map(function(v, i) { return 2 * (v - dea[i]); });
          
          var last = closes.length - 1;
          var price = closes[last];
          var ma20Val = ma20[last];
          var ma20Prev = ma20[last - 1];
          var difVal = dif[last];
          var deaVal = dea[last];
          var barVal = macdBar[last];
          var barPrev = macdBar[last - 1];
          
          var ret5 = (price / closes[last - 4] - 1) * 100;
          var ret20 = (price / closes[last - 19] - 1) * 100;
          
          // Conditions
          var aboveMA20 = price > ma20Val;
          var ma20Up = ma20Val > ma20Prev;
          var aboveZero = difVal > 0 && deaVal > 0;
          var goldenCross = difVal > deaVal && dif[last-1] <= dea[last-1];
          var redBar = barVal > 0;
          var barExpanding = barVal > barPrev;
          var ret5Above3 = ret5 > 3;
          var ret20Above10 = ret20 > 10;
          var beatBenchmark = ret20 > 11.16;
          
          // Score (12 max)
          var score = 0;
          if (aboveMA20) score += 1;
          if (ma20Up) score += 1;
          if (aboveZero) score += 1;
          if (goldenCross || (difVal > deaVal)) score += 1;
          if (redBar) score += 1;
          if (barExpanding) score += 1;
          if (ret5Above3) score += 1;
          if (ret20Above10) score += 1;
          if (beatBenchmark) score += 2;
          if (aboveZero && difVal > deaVal) score += 2;
          
          var stars = 1;
          if (score >= 10) stars = 5;
          else if (score >= 8) stars = 4;
          else if (score >= 6) stars = 3;
          else if (score >= 4) stars = 2;
          
          var starStr = '';
          for (var s = 0; s < stars; s++) starStr += '\u2B50';
          
          var signal = 'WAIT';
          if (aboveMA20 && ma20Up && difVal > deaVal) {
            if (aboveZero) signal = 'BUY';
            else signal = 'HOLD';
          } else if (aboveMA20) {
            signal = 'HOLD';
          }
          
          resolve({
            code: code,
            name: holdings.find(function(h){ return h.code===code; }).name,
            price: price.toFixed(3),
            ma20: ma20Val.toFixed(3),
            ma20Dir: ma20Up ? 'up' : 'down',
            dif: difVal.toFixed(4),
            dea: deaVal.toFixed(4),
            bar: barVal.toFixed(4),
            aboveZero: aboveZero,
            ret5: ret5.toFixed(1) + '%',
            ret20: ret20.toFixed(1) + '%',
            score: score,
            stars: stars,
            starStr: starStr,
            signal: signal,
            date: dates[last]
          });
        } catch(e) {
          resolve({ code: code, name: holdings.find(function(h){ return h.code===code; }).name, error: e.message });
        }
      });
    }).on('error', function(e) {
      resolve({ code: code, name: holdings.find(function(h){ return h.code===code; }).name, error: e.message });
    });
  });
}

async function main() {
  console.log('========================================');
  console.log('  1号策略持仓复盘 | 2026-04-18');
  console.log('========================================\n');
  
  for (var h of holdings) {
    var result = await fetchKline(h.code, h.market);
    if (result.error) {
      console.log(result.code + ' ' + result.name + ': ERROR - ' + result.error);
    } else {
      console.log(result.code + ' ' + result.name);
      console.log('  ' + result.date + '  close=' + result.price + '  MA20=' + result.ma20 + '  dir=' + result.ma20Dir);
      console.log('  DIF=' + result.dif + '  DEA=' + result.dea + '  bar=' + result.bar + '  zero=' + (result.aboveZero ? 'above' : 'below'));
      console.log('  5d=' + result.ret5 + '  20d=' + result.ret20);
      console.log('  score=' + result.score + '/12  ' + result.starStr + '  signal=' + result.signal);
    }
    console.log();
    await new Promise(function(r) { setTimeout(r, 100); });
  }
}

main();
