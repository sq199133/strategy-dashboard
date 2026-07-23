/**
 * 腾讯批量历史K线 + MA20 + MACD + 相关性矩阵扫描
 * 输出 corr_signals_YYYY-MM-DD.json
 */
const https = require('https');
const http = require('http');

function httpGet(url, timeoutMs = 10000) {
  return new Promise(resolve => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com' } }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => resolve(d));
    });
    req.on('error', () => resolve(''));
    req.setTimeout(timeoutMs, () => { req.destroy(); resolve(''); });
  });
}

async function fetchTencentKline(code, market, days = 60) {
  const sym = (market === 'SH' ? 'sh' : 'sz') + code;
  const url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayfqfund&param=' + sym + ',day,,,' + days + ',qfq';
  const raw = await httpGet(url);
  if (!raw) return null;
  try {
    const jsonStr = raw.replace(/^[^=]+=/, '');
    const json = JSON.parse(jsonStr);
    const fund = json.data && (json.data['sz' + code] || json.data['sh' + code]);
    if (!fund) return null;
    const dayArr = fund.qfqday || fund.day;
    if (!dayArr || dayArr.length < 5) return null;
    const closes = dayArr.map(k => parseFloat(k[2]));
    return { code, closes, name: fund.name || code };
  } catch(e) { return null; }
}

function ema(data, period) {
  const k = 2 / (period + 1);
  const r = [data[0]];
  for (let i = 1; i < data.length; i++) r.push(data[i] * k + r[i - 1] * (1 - k));
  return r;
}

function calcIndicators(closes) {
  if (!closes || closes.length < 25) return null;
  const ma20 = closes.slice(-20).reduce((s, v) => s + v, 0) / 20;
  const e12 = ema(closes, 12);
  const e26 = ema(closes, 26);
  const macdLine = closes.map((_, i) => e12[i] - e26[i]);
  const sig9 = ema(macdLine, 9);
  const macd = macdLine[macdLine.length - 1];
  const sig = sig9[sig9.length - 1];
  return {
    ma20,
    macdHist: macd - sig,
    aboveMA20: closes[closes.length - 1] > ma20,
    aboveZero: macd > 0,
  };
}

function pearson(x, y) {
  if (x.length < 10) return 0;
  const n = Math.min(x.length, y.length);
  let sx=0, sy=0, sxy=0, sx2=0, sy2=0;
  for (let i=0; i<n; i++) { sx+=x[i]; sy+=y[i]; sxy+=x[i]*y[i]; sx2+=x[i]*x[i]; sy2+=y[i]*y[i]; }
  const num = n*sxy - sx*sy;
  const den = Math.sqrt((n*sx2 - sx*sx) * (n*sy2 - sy*sy));
  return den === 0 ? 0 : num/den;
}

function calcReturns(closes) {
  const r = [];
  for (let i=1; i<closes.length; i++) {
    if (closes[i-1] > 0) r.push((closes[i] - closes[i-1]) / closes[i-1]);
  }
  return r;
}

async function main() {
  const POOL = require('D:/QClaw_Trading/data/etf_pool.js');
  const MAX_CORR = 0.70;
  const MAX_POSITIONS = 5;

  console.log('==========================================================');
  console.log('  相关性感知版ETF扫描  ' + new Date().toLocaleString('zh-CN'));
  console.log('==========================================================');

  // 批量获取历史K线
  console.log('\n[1] 批量获取历史K线（腾讯接口）...');
  const results = [];
  for (const etf of POOL) {
    const r = await fetchTencentKline(etf.code, etf.market, 60);
    const ind = r ? calcIndicators(r.closes) : null;
    if (r && ind) {
      const stars = (ind.aboveMA20 && ind.aboveZero) ? 2 : ind.aboveMA20 ? 1 : 0;
      const score = (ind.aboveMA20 ? 5 : 0) + (ind.aboveZero ? 5 : 0);
      results.push({
        code: etf.code, market: etf.market, name: etf.name,
        category: etf.category,
        closes: r.closes,
        price: r.closes[r.closes.length - 1],
        ma20: ind.ma20, macdHist: ind.macdHist,
        stars, score,
        aboveMA20: ind.aboveMA20, aboveZero: ind.aboveZero,
      });
    }
    process.stdout.write('  ' + etf.code + '  ');
    if ((results.length + POOL.filter((_, i) => i < POOL.indexOf(etf)).length) % 10 === 0) process.stdout.write('\n');
    await new Promise(res => setTimeout(res, 200));
  }
  console.log('\n\n  完成: ' + results.length + '/' + POOL.length + ' 只');

  // 信号统计
  const twoStars = results.filter(s => s.stars >= 2).sort((a, b) => b.score - a.score);
  const oneStar = results.filter(s => s.stars === 1).sort((a, b) => b.score - a.score);
  console.log('\n[2] 信号统计');
  console.log('  ⭐⭐买入: ' + twoStars.length + '  ⭐持股: ' + oneStar.length + '  ⏸: ' + (results.length - twoStars.length - oneStar.length));

  if (twoStars.length === 0) { console.log('无买入信号'); process.exit(0); }

  // Pearson相关性矩阵
  console.log('\n[3] 计算相关性矩阵...');
  const list = twoStars.filter(s => s.closes && s.closes.length >= 25);
  const matrix = {};
  const retMap = {};
  list.forEach(s => { retMap[s.code] = calcReturns(s.closes); });
  for (let i = 0; i < list.length; i++) {
    matrix[list[i].code] = {};
    for (let j = 0; j < list.length; j++) {
      if (i === j) matrix[list[i].code][list[j].code] = 1;
      else if (j < i) matrix[list[i].code][list[j].code] = matrix[list[j].code][list[i].code];
      else matrix[list[i].code][list[j].code] = parseFloat(pearson(retMap[list[i].code], retMap[list[j].code]).toFixed(3));
    }
  }

  // 打印矩阵
  const nm = {};
  list.forEach(s => { nm[s.code] = s.name; });
  const pad = s => (s||'').substring(0,7).padEnd(8);
  const codes = list.map(s => s.code);
  console.log('\n  === 相关性矩阵 (' + list.length + ' 只, 60日Pearson) ===');
  console.log('          ' + codes.map(c => pad(nm[c])).join(''));
  codes.forEach(ci => {
    let row = pad(nm[ci] || ci);
    codes.forEach(cj => {
      const ii = codes.indexOf(ci), ij = codes.indexOf(cj);
      if (ii === ij) row += '  1.000  ';
      else if (ij < ii) row += '  ----   ';
      else {
        const v = matrix[ci][cj];
        const icon = v > 0.8 ? 'R' : v > 0.6 ? 'O' : v > 0.4 ? 'Y' : 'G';
        row += ' ' + icon + v.toFixed(2) + '  ';
      }
    });
    console.log(row);
  });
  console.log('  R>0.8  O>0.6  Y>0.4  G<0.4');

  // 贪心低相关选择
  const sorted = [...list].sort((a, b) => b.score - a.score);
  const selected = [];
  const selCodes = new Set();
  console.log('\n[4] 低相关性选择(maxCorr=' + MAX_CORR + '):');
  for (const sig of sorted) {
    if (selCodes.size >= MAX_POSITIONS) { console.log('  满仓: ' + sig.code + ' ' + sig.name); break; }
    let maxC = 0;
    for (const sc of selCodes) {
      if (matrix[sig.code] && matrix[sig.code][sc] !== undefined) {
        maxC = Math.max(maxC, Math.abs(matrix[sig.code][sc]));
      }
    }
    const ok = maxC <= MAX_CORR || maxC === 0;
    console.log('  ' + (ok ? 'OK' : 'NO') + ' ' + sig.code + ' ' + sig.name.substring(0,8) + ' [maxC=' + maxC.toFixed(2) + ']');
    if (ok) { selected.push(sig); selCodes.add(sig.code); }
  }

  // 最终输出
  console.log('\n==========================================================');
  console.log('  推荐持仓 (' + selected.length + ' 只)');
  console.log('==========================================================');
  selected.forEach((s, i) => {
    console.log('  ' + (i+1) + '. ' + s.code + ' ' + s.name + ' [' + s.category + ']');
    console.log('     price=' + s.price.toFixed(4) + ' MA20=' + s.ma20.toFixed(4) + ' MACD=' + s.macdHist.toFixed(4) + ' stars=' + s.stars);
    const pairs = [];
    selected.forEach((s2, j) => {
      if (i !== j && matrix[s.code]) {
        const v = matrix[s.code][s2.code];
        if (v !== undefined) pairs.push(s2.name + '=' + v.toFixed(2));
      }
    });
    console.log('     组内corr: ' + (pairs.join(' | ') || '-'));
  });

  const naive = twoStars.slice(0, MAX_POSITIONS);
  console.log('\n  对比:');
  console.log('  纯信号TOP' + MAX_POSITIONS + ': ' + naive.map(s => s.name).join(', '));
  console.log('  低相关组合: ' + selected.map(s => s.name).join(', '));
  const diff = selected.filter(s => !naive.find(n => n.code === s.code));
  const missed = naive.filter(s => !selected.find(x => x.code === s.code));
  if (diff.length > 0) console.log('  低相关新增: ' + diff.map(s => s.name + '(' + s.category + ')').join(', '));
  if (missed.length > 0) console.log('  被排除(相关过高): ' + missed.map(s => s.name).join(', '));

  const out = {
    date: new Date().toISOString().slice(0, 10),
    poolSize: POOL.length,
    twoStarCount: twoStars.length,
    maxCorr: MAX_CORR,
    recommended: selected.map(s => ({
      code: s.code, name: s.name, market: s.market, category: s.category,
      price: s.price.toFixed(4), ma20: s.ma20.toFixed(4),
      macdHist: s.macdHist.toFixed(4), stars: s.stars
    })),
    naiveTop: naive.map(s => ({ code: s.code, name: s.name })),
  };

  const fs = require('fs');
  fs.writeFileSync(__dirname + '/corr_signals_' + out.date + '.json', JSON.stringify(out, null, 2));
  console.log('\n[OK] 已保存: corr_signals_' + out.date + '.json');
}

main().catch(console.error);
