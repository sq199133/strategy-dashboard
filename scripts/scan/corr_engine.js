/**
 * ETF相关性引擎 v1.0
 * 提供：fetchHistory, calcReturns, pearsonCorr, calcCorrMatrix, selectDiversified, printCorrMatrix
 */
const https = require('https');
const http = require('http');

// ─────────────────────────────────────────────────────────
// HTTP helper
// ─────────────────────────────────────────────────────────
function httpGet(url, timeoutMs = 8000) {
  const mod = url.startsWith('https') ? https : http;
  return new Promise(resolve => {
    const req = mod.get(url, { headers: { 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.eastmoney.com' } }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => resolve(d));
    });
    req.on('error', () => resolve(''));
    req.setTimeout(timeoutMs, () => { req.destroy(); resolve(''); });
  });
}

// ─────────────────────────────────────────────────────────
// 获取历史收盘价
// ─────────────────────────────────────────────────────────
function fetchEMHistory(code, market, days = 60) {
  const mkt = market === 'SH' ? 1 : 0;
  const url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=' + mkt + '.' + code + '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&end=20500101&lmt=' + days;
  return httpGet(url).then(d => {
    try {
      const json = JSON.parse(d);
      if (json.data && json.data.klines && json.data.klines.length > 0) {
        const closes = json.data.klines.map(k => parseFloat(k.split(',')[2]));
        return { code, closes, name: json.data.name || code };
      }
    } catch (e) { /* ignore */ }
    return { code, closes: [], name: code };
  });
}

// ─────────────────────────────────────────────────────────
// 收益率序列
// ─────────────────────────────────────────────────────────
function calcReturns(closes) {
  const rets = [];
  for (let i = 1; i < closes.length; i++) {
    if (closes[i - 1] > 0) rets.push((closes[i] - closes[i - 1]) / closes[i - 1]);
  }
  return rets;
}

// ─────────────────────────────────────────────────────────
// Pearson相关系数
// ─────────────────────────────────────────────────────────
function pearsonCorr(x, y) {
  if (x.length < 10 || y.length < 10) return 0;
  const n = Math.min(x.length, y.length);
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
  for (let i = 0; i < n; i++) {
    sumX += x[i]; sumY += y[i];
    sumXY += x[i] * y[i];
    sumX2 += x[i] * x[i];
    sumY2 += y[i] * y[i];
  }
  const num = n * sumXY - sumX * sumY;
  const den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
  return den === 0 ? 0 : num / den;
}

// ─────────────────────────────────────────────────────────
// 批量获取 + 相关性矩阵
// ─────────────────────────────────────────────────────────
async function calcCorrMatrix(etfList, days = 60) {
  console.log('  拉取历史数据 (' + days + '天)');
  const results = [];
  for (const e of etfList) {
    const r = await fetchEMHistory(e.code, e.market, days);
    r.name = e.name;
    r.returns = calcReturns(r.closes);
    const status = r.returns.length > 0 ? '✅' + r.returns.length + '天' : '❌无数据';
    console.log('  ' + e.code + ' ' + e.name.substring(0, 6) + ': ' + status);
    await new Promise(res => setTimeout(res, 120));
  }

  const codes = results.map(r => r.code);
  const matrix = {};
  for (let i = 0; i < results.length; i++) {
    matrix[codes[i]] = {};
    for (let j = 0; j < results.length; j++) {
      if (i === j) {
        matrix[codes[i]][codes[j]] = 1;
      } else if (j < i) {
        matrix[codes[i]][codes[j]] = matrix[codes[j]][codes[i]];
      } else {
        matrix[codes[i]][codes[j]] = parseFloat(pearsonCorr(results[i].returns, results[j].returns).toFixed(3));
      }
    }
  }
  return { matrix, etfs: results };
}

// ─────────────────────────────────────────────────────────
// 贪心低相关性选择
// ─────────────────────────────────────────────────────────
function selectDiversified(signals, existingHoldings, corrMatrix, maxCorr = 0.70, maxTotal = 5) {
  const selected = [...existingHoldings];
  const selectedCodes = new Set(existingHoldings.map(h => h.code));

  const sorted = [...signals].sort((a, b) => b.score - a.score);

  console.log('\n  选择过程（按信号强度排序）：');
  for (const sig of sorted) {
    if (selectedCodes.size >= maxTotal) { console.log('  ' + sig.code + ' 满仓，跳过'); break; }

    let maxCorrVal = 0;
    for (const sc of selectedCodes) {
      if (corrMatrix[sig.code] && corrMatrix[sig.code][sc] !== undefined) {
        const c = Math.abs(corrMatrix[sig.code][sc]);
        if (c > maxCorrVal) maxCorrVal = c;
      }
    }

    const ok = maxCorrVal <= maxCorr || maxCorrVal === 0;
    const mark = ok ? '✅' : '❌';
    const reason = ok ? '加入(maxCorr=' + maxCorrVal.toFixed(2) + ')' : '排除(相关=' + maxCorrVal.toFixed(2) + '>' + maxCorr + ')';
    console.log('  ' + mark + ' ' + sig.code + ' ' + sig.name.substring(0, 8) + ' ' + reason);
    if (ok) { selected.push(sig); selectedCodes.add(sig.code); }
  }
  return selected;
}

// ─────────────────────────────────────────────────────────
// 打印相关性矩阵
// ─────────────────────────────────────────────────────────
function printCorrMatrix(matrix, etfs) {
  const codes = Object.keys(matrix);
  const nameMap = {};
  etfs.forEach(e => nameMap[e.code] = e.name);

  const maxLen = 7;
  const pad = n => n.substring(0, maxLen).padEnd(maxLen + 1);
  const header = '         ' + codes.map(c => pad(nameMap[c] || c)).join('');
  console.log('\n  ═══ 相关性矩阵（' + codes.length + '只，60日Pearson）═══');
  console.log(header);
  codes.forEach(ci => {
    let row = pad(nameMap[ci] || ci);
    codes.forEach(cj => {
      if (ci === cj) {
        row += '  1.000  ';
      } else if (codes.indexOf(cj) < codes.indexOf(ci)) {
        row += '  ----   ';
      } else {
        const v = matrix[ci][cj];
        const color = v > 0.80 ? '🔴' : v > 0.60 ? '🟠' : v > 0.40 ? '🟡' : '🟢';
        row += color + v.toFixed(2) + '  ';
      }
    });
    console.log(row);
  });
  console.log('  图例: 🔴>0.80(高度相关) 🟠>0.60 🟡>0.40 🟢≤0.40(低相关/可分散)');
}

module.exports = { fetchEMHistory, calcReturns, pearsonCorr, calcCorrMatrix, selectDiversified, printCorrMatrix };
