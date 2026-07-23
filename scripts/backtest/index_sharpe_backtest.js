// index_sharpe_backtest.js
// 3-year rolling Sharpe > 1 backtest on INDEX data (from inception)
// Uses curl.exe to fetch from Tencent API

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const DATA_DIR = 'D:/QClaw_Trading/data/index_history';
const POOL_FILE = 'D:/QClaw_Trading/scripts/scan/etf_pool.json';
const RESULT_FILE = 'D:/QClaw_Trading/scripts/backtest/index_sharpe_results.json';
const REPORT_FILE = 'D:/QClaw_Trading/scripts/backtest/index_sharpe_report.txt';

// === Index code mapping (index name -> Tencent API code) ===
const INDEX_MAP = {
  // Broad market
  '\u6caa\u6df1300': 'sh000300',
  '\u4e0a\u8bc150': 'sh000016',
  '\u4e2d\u8bc1500': 'sh000905',
  '\u4e2d\u8bc11000': 'sh000852',
  '\u4e2d\u8bc1800': 'sh000906',
  '\u6df1\u8bc1100': 'sz399330',
  '\u521b\u4e1a\u677f': 'sz399006',
  '\u521b\u4e1a\u677f50': 'sz399673',
  '\u79d1\u521b50': 'sh000688',
  '\u79d1\u521b100': 'sh000698',
  '\u4e2d\u8bc1A500': 'sh932050',
  '\u4e2d\u8bc1A50': 'sh930050',
  '\u4e2d\u8bc1A100': 'sh000308',
  '\u4e2d\u8bc12000': 'sh932000',
  '\u53cc\u521b50': 'sz399673',
  'MSCI\u4e2d\u56fdA50': 'sh746460',
  '\u79d1\u521b200': 'sh000699',
  '\u79d1\u521b\u7efc\u6307': 'sh000700',
  // Strategy
  '\u7ea2\u5229': 'sh000922',
  '\u4e2d\u8bc1\u7ea2\u5229': 'sh000922',
  '\u7ea2\u5229\u4f4e\u6ce2': 'shH30269',
  '\u592e\u4f01\u7ea2\u5229': 'sh000813',
  '\u6210\u957f': 'sz399377',
  '\u4ef7\u503c': 'sz399378',
  '\u6caa\u6df1300\u589e\u5f3a': 'sh000300',
  '\u4e2d\u8bc1500\u589e\u5f3a': 'sh000905',
  '\u4e2d\u8bc11000\u589e\u5f3a': 'sh000852',
  '\u79d1\u521b50\u589e\u5f3a': 'sh000688',
  '\u4e2d\u8bc1A500\u589e\u5f3a': 'sh932050',
  // Tech
  '\u91d1\u878d\u79d1\u6280': 'sz399998',
  '\u673a\u5668\u4eba': 'sh930049',
  '\u8f6f\u4ef6': 'sz399766',
  '\u4eba\u5de5\u667a\u80fd': 'sh930713',
  '\u82af\u7247': 'sz399998',
  '\u534a\u5bfc\u4f53': 'sh931865',
  '\u901a\u4fe1': 'sz399825',
  '\u4e91\u8ba1\u7b97': 'sh930776',
  '\u79d1\u521b\u4fe1\u606f': 'sh000697',
  '\u79d1\u521b\u534a\u5bfc\u4f53': 'sh000688',
  '\u79d1\u521b\u82af\u7247': 'sh000688',
  '\u79d1\u521b\u4eba\u5de5\u667a\u80fd': 'sh000688',
  // Healthcare
  '\u4e2d\u836f': 'sz399394',
  '\u751f\u7269\u79d1\u6280': 'sz399441',
  '\u533b\u836f': 'sh000933',
  '\u533b\u7597': 'sz399989',
  '\u521b\u65b0\u836f': 'sz399992',
  '\u79d1\u521b\u533b\u836f': 'sh000688',
  // Finance
  '\u5238\u5546': 'sh000819',
  '\u91d1\u878d': 'sh000934',
  '\u8bc1\u5238\u4fdd\u9669': 'sz399967',
  '\u94f6\u884c': 'sh000803',
  '\u8bc1\u5238': 'sh000819',
  // Consumer
  '\u6c7d\u8f66\u96f6\u90e8\u4ef6': 'sz399932',
  '\u5bb6\u7535': 'sz399996',
  '\u98df\u54c1\u996e\u6599': 'sz399397',
  '\u6d88\u8d39': 'sz399932',
  '\u767d\u9152': 'sz399997',
  '\u6c7d\u8f66': 'sz399932',
  // New Energy
  '\u7535\u6c60': 'sz399938',
  '\u7535\u7f51\u8bbe\u5907': 'sh930036',
  '\u7eff\u8272\u7535\u529b': 'sh930022',
  '\u78b3\u4e2d\u548c': 'sh930018',
  '\u65b0\u80fd\u6e90\u8f66': 'sz399976',
  '\u5149\u4f0f': 'sz399808',
  '\u65b0\u80fd\u6e90': 'sz399808',
  // Commodities
  '\u5316\u5de5': 'sz399938',
  '\u6709\u8272\u91d1\u5c5e': 'sh931924',
  '\u7164\u70ad': 'sh931901',
  '\u9ec4\u91d1\u80a1': 'sh931038',
  '\u9ec4\u91d1': 'sh931038',
  // Manufacturing
  '\u519b\u5de5': 'sz399967',
  '\u519b\u5de5\u9f99\u5934': 'sz399967',
  // Real estate
  '\u623f\u5730\u4ea7': 'sz399393',
  // Utilities
  '\u7535\u529b': 'sz399811',
  // Agriculture
  '\u755c\u7267\u517b\u6b96': 'sz399926',
  // Media
  '\u4f20\u5a92': 'sz399973',
  '\u6e38\u620f': 'sz399975',
  // Cross-border
  '\u6052\u751f\u751f\u7269\u79d1\u6280': 'hkHSTECH',
  '\u6052\u751f\u79d1\u6280': 'hkHSTECH',
  '\u6052\u751f\u6307\u6570': 'hkHSI',
  '\u6052\u751f\u56fd\u4f01': 'hkHSCEI',
  '\u6052\u751f\u4e92\u8054\u7f51': 'hkHSI',
  '\u6052\u751f\u533b\u7597': 'hkHSTECH',
  '\u7eb3\u65af\u8fbe\u514b100': 'usNDX',
  '\u6807\u666e500': 'usSPX',
  '\u4e2d\u6982\u4e92\u8054': 'sz399998',
  '\u6e2f\u80a1\u901a\u6c7d\u8f66': 'hkHSI',
  '\u6e2f\u80a1\u901a\u521b\u65b0\u836f': 'hkHSTECH',
  '\u6e2f\u80a1\u901a\u4e92\u8054\u7f51': 'hkHSTECH',
  '\u6e2f\u80a1\u901a\u7ea2\u5229': 'hkHSI',
  '\u4e1c\u5357\u4e9a\u79d1\u6280': 'hkHSI',
};

// Ensure data directory exists
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

// Load ETF pool
const pool = JSON.parse(fs.readFileSync(POOL_FILE, 'utf8'));
const log = [];
function p(s) { log.push(s); console.log(s); }

p('=== 3-Year Rolling Sharpe > 1 Backtest (Index Data) ===');
p('ETF Pool: ' + pool.length + ' ETFs');
p('');

// Step 1: Map ETFs to index codes and fetch data
const indexList = []; // unique indices
const etfToIndex = {}; // etf code -> index code

for (const etf of pool) {
  const idxName = etf.index;
  let idxCode = INDEX_MAP[idxName];
  if (!idxCode) {
    // Try to guess: for "增强" versions, use the base index
    if (idxName.includes('\u589e\u5f3a')) {
      const baseName = idxName.replace('\u589e\u5f3a', '');
      idxCode = INDEX_MAP[baseName] || INDEX_MAP[baseName + '\u589e\u5f3a'];
    }
  }
  etfToIndex[etf.market.toLowerCase() + etf.code] = idxCode || null;
  if (idxCode && !indexList.find(i => i.code === idxCode)) {
    indexList.push({ code: idxCode, name: idxName });
  }
}

p('Unique indices: ' + indexList.length);
p('ETFs with mapping: ' + Object.values(etfToIndex).filter(v => v).length + '/' + pool.length);
p('');

// Step 2: Fetch index data
function fetchIndexData(idxCode) {
  const outFile = path.join(DATA_DIR, idxCode.replace(/[\\/:]/g, '_') + '.json');
  if (fs.existsSync(outFile)) {
    try {
      const existing = JSON.parse(fs.readFileSync(outFile, 'utf8'));
      if (existing.records && existing.records.length > 100) {
        return existing;
      }
    } catch (e) { /* refetch */ }
  }

  const allRecords = [];
  let endDate = '';
  let maxPages = 20; // safety limit

  while (maxPages-- > 0) {
    const param = idxCode + ',day,,' + endDate + ',640,';
    const url = 'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + param;
    let rawData;
    try {
      rawData = execSync('curl.exe -sL "' + url + '"', { encoding: 'utf8', timeout: 30000 });
    } catch (e) {
      p('  FETCH ERROR: ' + idxCode + ' ' + e.message.slice(0, 80));
      break;
    }

    let parsed;
    try {
      parsed = JSON.parse(rawData);
    } catch (e) {
      p('  PARSE ERROR: ' + idxCode);
      break;
    }

    if (parsed.code !== 0 || !parsed.data) {
      p('  API ERROR: ' + idxCode + ' code=' + parsed.code);
      break;
    }

    // Find the key in data (could be idxCode or different)
    const dataKey = Object.keys(parsed.data).find(k => k !== 'mx_price' && k !== 'prec' && k !== 'version');
    if (!dataKey) {
      p('  NO DATA KEY: ' + idxCode);
      break;
    }

    const dayData = parsed.data[dataKey].day;
    if (!dayData || dayData.length === 0) {
      break; // no more data
    }

    // dayData format: [[date, open, close, high, low, volume], ...]
    for (const d of dayData) {
      allRecords.push({
        date: d[0],
        open: parseFloat(d[1]),
        close: parseFloat(d[2]),
        high: parseFloat(d[3]),
        low: parseFloat(d[4]),
        vol: parseFloat(d[5]) || 0
      });
    }

    // Set endDate for next page (earliest date - 1 day)
    endDate = dayData[0][0]; // earliest in this batch
    if (dayData.length < 640) break; // last page
  }

  // Sort by date ascending and deduplicate
  allRecords.sort((a, b) => a.date.localeCompare(b.date));
  const unique = [];
  let lastDate = '';
  for (const r of allRecords) {
    if (r.date !== lastDate && r.close > 0) {
      unique.push(r);
      lastDate = r.date;
    }
  }

  const result = { code: idxCode, records: unique, fetchedAt: new Date().toISOString() };
  fs.writeFileSync(outFile, JSON.stringify(result), 'utf8');
  return result;
}

p('--- Fetching Index Data ---');
const indexData = {};
let fetchOk = 0, fetchFail = 0;
for (const idx of indexList) {
  try {
    const data = fetchIndexData(idx.code);
    if (data.records && data.records.length > 0) {
      indexData[idx.code] = data;
      const start = data.records[0].date;
      const end = data.records[data.records.length - 1].date;
      const yrs = ((new Date(end) - new Date(start)) / (365.25 * 86400000)).toFixed(1);
      p('  OK ' + idx.code + ' (' + idx.name + '): ' + data.records.length + ' days, ' + start + ' -> ' + end + ' (' + yrs + 'yr)');
      fetchOk++;
    } else {
      p('  EMPTY ' + idx.code + ' (' + idx.name + ')');
      fetchFail++;
    }
  } catch (e) {
    p('  FAIL ' + idx.code + ' (' + idx.name + '): ' + e.message.slice(0, 80));
    fetchFail++;
  }
}
p('Fetched: ' + fetchOk + ' OK, ' + fetchFail + ' failed');
p('');

// Step 3: Calculate 3-year rolling Sharpe and backtest
const WIN = 756; // 3 years * 252 trading days
const SHARPE_BUY = 1.0;
const SHARPE_SELL = 1.0;

function rollingSharpe(prices, win) {
  // Calculate rolling annualized Sharpe ratio
  const n = prices.length;
  const sharpe = new Array(n).fill(null);
  
  for (let i = win; i < n; i++) {
    // Calculate returns in the window
    let sumR = 0, sumR2 = 0;
    for (let j = i - win + 1; j <= i; j++) {
      const r = (prices[j] / prices[j - 1]) - 1;
      sumR += r;
      sumR2 += r * r;
    }
    const meanR = sumR / win;
    const varR = (sumR2 / win) - (meanR * meanR);
    const stdR = Math.sqrt(Math.max(varR, 0));
    
    if (stdR > 0.0001) {
      sharpe[i] = (meanR * 252) / (stdR * Math.sqrt(252));
    }
  }
  return sharpe;
}

function backtestSharpe(prices, dates, win, buyThr, sellThr) {
  const n = prices.length;
  const sharpe = rollingSharpe(prices, win);
  
  let inPos = false;
  let entryPrice = 0;
  let entryDate = '';
  const trades = [];
  const equity = [1.0];
  
  for (let i = 1; i < n; i++) {
    const dailyRet = (prices[i] / prices[i - 1]) - 1;
    const prevEq = equity[equity.length - 1];
    
    if (i < win || sharpe[i] === null) {
      // No signal yet, stay out
      equity.push(prevEq);
      continue;
    }
    
    if (!inPos) {
      if (sharpe[i] >= buyThr) {
        inPos = true;
        entryPrice = prices[i];
        entryDate = dates[i];
      }
      equity.push(prevEq); // no return when out
    } else {
      if (sharpe[i] < sellThr) {
        // Sell signal
        const exitPrice = prices[i];
        const tradeRet = (exitPrice / entryPrice) - 1;
        const tradeDays = i - prices.indexOf(entryPrice);
        trades.push({
          entry: entryDate,
          exit: dates[i],
          entryPrice: entryPrice.toFixed(4),
          exitPrice: exitPrice.toFixed(4),
          ret: (tradeRet * 100).toFixed(2) + '%'
        });
        inPos = false;
        equity.push(prevEq * (1 + dailyRet)); // earn today's return then exit
      } else {
        equity.push(prevEq * (1 + dailyRet)); // earn daily return while in position
      }
    }
  }
  
  // Close any open position at end
  if (inPos) {
    trades.push({
      entry: entryDate,
      exit: dates[n - 1] + ' (open)',
      entryPrice: entryPrice.toFixed(4),
      exitPrice: prices[n - 1].toFixed(4),
      ret: ((prices[n - 1] / entryPrice - 1) * 100).toFixed(2) + '%'
    });
  }
  
  return { equity, trades, sharpe };
}

function calcStats(equity) {
  const n = equity.length;
  if (n < 10) return null;
  
  const totalRet = equity[n - 1] / equity[0] - 1;
  const years = n / 252;
  const ann = Math.pow(equity[n - 1] / equity[0], 1 / years) - 1;
  
  // Max drawdown
  let peak = equity[0];
  let maxDD = 0;
  for (let i = 1; i < n; i++) {
    if (equity[i] > peak) peak = equity[i];
    const dd = (peak - equity[i]) / peak;
    if (dd > maxDD) maxDD = dd;
  }
  
  // Sharpe from daily returns
  let sumR = 0, sumR2 = 0, count = 0;
  for (let i = 1; i < n; i++) {
    const r = equity[i] / equity[i - 1] - 1;
    sumR += r;
    sumR2 += r * r;
    count++;
  }
  const meanR = sumR / count;
  const stdR = Math.sqrt((sumR2 / count) - (meanR * meanR));
  const sharpe = stdR > 0 ? (meanR * 252) / (stdR * Math.sqrt(252)) : 0;
  
  // Win rate (positive days)
  let winDays = 0;
  for (let i = 1; i < n; i++) {
    if (equity[i] > equity[i - 1]) winDays++;
  }
  
  return {
    totalRet: totalRet * 100,
    ann: ann * 100,
    maxDD: maxDD * 100,
    sharpe,
    winRate: (winDays / (n - 1)) * 100,
    years
  };
}

p('--- Backtest Results (3yr Rolling Sharpe > ' + SHARPE_BUY + ') ---');
p('');

const results = [];
const etfResults = [];

for (const etf of pool) {
  const etfKey = etf.market.toLowerCase() + etf.code;
  const idxCode = etfToIndex[etfKey];
  if (!idxCode || !indexData[idxCode]) {
    continue;
  }
  
  const data = indexData[idxCode];
  const prices = data.records.map(r => r.close);
  const dates = data.records.map(r => r.date);
  
  if (prices.length < WIN + 60) {
    continue; // not enough data for 3-year window + some trades
  }
  
  // Backtest: Rolling Sharpe strategy
  const { equity, trades, sharpe } = backtestSharpe(prices, dates, WIN, SHARPE_BUY, SHARPE_SELL);
  
  // Buy-and-hold benchmark (same period)
  const bhEquity = [1.0];
  for (let i = 1; i < equity.length; i++) {
    const dailyRet = (prices[i] / prices[i - 1]) - 1;
    bhEquity.push(bhEquity[bhEquity.length - 1] * (1 + dailyRet));
  }
  
  const stats = calcStats(equity);
  const bhStats = calcStats(bhEquity);
  
  if (!stats) continue;
  
  // Count days in market
  let inMarketDays = 0;
  for (let i = 1; i < equity.length; i++) {
    if (equity[i] !== equity[i - 1]) inMarketDays++;
  }
  // Actually count from trades
  let totalTradeDays = 0;
  for (const t of trades) {
    totalTradeDays++; // approximate
  }
  
  const result = {
    code: etf.market + etf.code,
    name: etf.name,
    index: etf.index,
    indexCode: idxCode,
    category: etf.category,
    startDate: dates[0],
    endDate: dates[dates.length - 1],
    dataYears: ((new Date(dates[dates.length - 1]) - new Date(dates[0])) / (365.25 * 86400000)).toFixed(1),
    tradeCount: trades.length,
    strategy: stats,
    buyHold: bhStats,
    excessAnn: stats.ann - (bhStats ? bhStats.ann : 0)
  };
  
  results.push(result);
  etfResults.push(result);
}

// Sort by Sharpe descending
results.sort((a, b) => b.strategy.sharpe - a.strategy.sharpe);

p('ETFs with enough data (3yr+): ' + results.length);
p('');

// Summary table
p('Code        Name                       IdxCode    Yrs  Sharpe  Ann%    DD%   Trades  BH_Ann%  Excess%');
p('-'.repeat(110));
for (const r of results) {
  const flag = r.strategy.sharpe >= 1.0 ? '*' : (r.strategy.sharpe >= 0.5 ? '+' : ' ');
  p(flag + r.code.padEnd(12) + r.name.slice(0, 12).padEnd(12) + '  ' + r.indexCode.padEnd(10) + ' ' + r.dataYears.padStart(4) + '  ' + r.strategy.sharpe.toFixed(2).padStart(6) + '  ' + r.strategy.ann.toFixed(1).padStart(5) + '%  ' + r.strategy.maxDD.toFixed(1).padStart(5) + '%  ' + String(r.tradeCount).padStart(6) + '  ' + (r.buyHold ? r.buyHold.ann.toFixed(1) : 'N/A').padStart(6) + '%  ' + r.excessAnn.toFixed(1).padStart(6) + '%');
}

p('');
p('(* Sharpe>=1.0, + Sharpe>=0.5)');

// Category summary
p('');
p('=== Category Summary ===');
const catStats = {};
for (const r of results) {
  if (!catStats[r.category]) catStats[r.category] = [];
  catStats[r.category].push(r);
}
for (const [cat, arr] of Object.entries(catStats).sort((a, b) => {
  const avgA = a[1].reduce((s, r) => s + r.strategy.sharpe, 0) / a[1].length;
  const avgB = b[1].reduce((s, r) => s + r.strategy.sharpe, 0) / b[1].length;
  return avgB - avgA;
})) {
  const avgSharpe = arr.reduce((s, r) => s + r.strategy.sharpe, 0) / arr.length;
  const avgAnn = arr.reduce((s, r) => s + r.strategy.ann, 0) / arr.length;
  const avgDD = arr.reduce((s, r) => s + r.strategy.maxDD, 0) / arr.length;
  const bestSharpe = Math.max(...arr.map(r => r.strategy.sharpe));
  p(cat.padEnd(12) + ' | ' + arr.length + ' ETFs | AvgSharpe=' + avgSharpe.toFixed(2) + ' AvgAnn=' + avgAnn.toFixed(1) + '% AvgDD=' + avgDD.toFixed(1) + '% Best=' + bestSharpe.toFixed(2));
}

// Portfolio simulation (equal weight, rebalance when signals change)
p('');
p('=== Portfolio Simulation ===');
// Find common period
let commonStart = '9999', commonEnd = '0000';
for (const r of results) {
  if (r.startDate > commonStart) commonStart = r.startDate; // no wait, we want the LATEST start
  if (r.endDate < commonEnd) commonEnd = r.endDate; // earliest end
}
// Actually for portfolio, we should use the dates where at least some ETFs have data
// Let's just compute a simple equal-weight portfolio of ALL qualifying ETFs

// For each qualifying ETF, we have equity curve from index data
// Rebuild portfolio NAV
const portfolioETFs = results.filter(r => r.strategy.sharpe > 0);
p('Portfolio candidates (Sharpe > 0): ' + portfolioETFs.length + ' ETFs');

// Build equal-weight portfolio NAV
const portEquity = {};
for (const r of portfolioETFs) {
  const data = indexData[r.indexCode];
  const prices = data.records.map(rec => rec.close);
  const dates = data.records.map(rec => rec.date);
  const { equity } = backtestSharpe(prices, dates, WIN, SHARPE_BUY, SHARPE_SELL);
  for (let i = 0; i < dates.length; i++) {
    if (!portEquity[dates[i]]) portEquity[dates[i]] = { sum: 0, count: 0 };
    portEquity[dates[i]].sum += equity[i];
    portEquity[dates[i]].count++;
  }
}

// Compute portfolio NAV
const portDates = Object.keys(portEquity).sort();
const portNAV = portDates.map(d => portEquity[d].sum / portEquity[d].count);
const portStats = calcStats(portNAV);

// Buy-and-hold benchmark for same period
const bhPortEquity = {};
for (const r of portfolioETFs) {
  const data = indexData[r.indexCode];
  const prices = data.records.map(rec => rec.close);
  const dates = data.records.map(rec => rec.date);
  const bhEq = [1.0];
  for (let i = 1; i < prices.length; i++) {
    bhEq.push(bhEq[bhEq.length - 1] * (prices[i] / prices[i - 1]));
  }
  for (let i = 0; i < dates.length; i++) {
    if (!bhPortEquity[dates[i]]) bhPortEquity[dates[i]] = { sum: 0, count: 0 };
    bhPortEquity[dates[i]].sum += bhEq[i];
    bhPortEquity[dates[i]].count++;
  }
}
const bhPortDates = Object.keys(bhPortEquity).sort();
const bhPortNAV = bhPortDates.map(d => bhPortEquity[d].sum / bhPortEquity[d].count);
const bhPortStats = calcStats(bhPortNAV);

if (portStats) {
  p('');
  p('Portfolio (equal-weight, ' + portfolioETFs.length + ' ETFs):');
  p('  Strategy:  Sharpe=' + portStats.sharpe.toFixed(2) + '  Ann=' + portStats.ann.toFixed(1) + '%  MaxDD=' + portStats.maxDD.toFixed(1) + '%  Years=' + portStats.years.toFixed(1));
  if (bhPortStats) {
    p('  Buy&Hold:  Sharpe=' + bhPortStats.sharpe.toFixed(2) + '  Ann=' + bhPortStats.ann.toFixed(1) + '%  MaxDD=' + bhPortStats.maxDD.toFixed(1) + '%');
    p('  Excess:    +' + (portStats.ann - bhPortStats.ann).toFixed(1) + '%/yr');
  }
}

// Overall stats
p('');
p('=== Overall Stats ===');
const allSharpes = results.map(r => r.strategy.sharpe);
const avgSharpe = allSharpes.reduce((a, b) => a + b, 0) / allSharpes.length;
const sharpeGt1 = results.filter(r => r.strategy.sharpe >= 1.0).length;
const sharpeGt05 = results.filter(r => r.strategy.sharpe >= 0.5).length;
const sharpeGt0 = results.filter(r => r.strategy.sharpe > 0).length;
const avgExcess = results.reduce((s, r) => s + r.excessAnn, 0) / results.length;
const beatBH = results.filter(r => r.excessAnn > 0).length;

p('Total ETFs tested: ' + results.length);
p('Sharpe >= 1.0: ' + sharpeGt1 + ' (' + (sharpeGt1 / results.length * 100).toFixed(0) + '%)');
p('Sharpe >= 0.5: ' + sharpeGt05 + ' (' + (sharpeGt05 / results.length * 100).toFixed(0) + '%)');
p('Sharpe > 0:   ' + sharpeGt0 + ' (' + (sharpeGt0 / results.length * 100).toFixed(0) + '%)');
p('Avg Sharpe: ' + avgSharpe.toFixed(3));
p('Beat Buy&Hold: ' + beatBH + '/' + results.length + ' (' + (beatBH / results.length * 100).toFixed(0) + '%)');
p('Avg Excess Ann: ' + avgExcess.toFixed(1) + '%/yr');

// Save results
const saveData = {
  config: { window: WIN, buyThreshold: SHARPE_BUY, sellThreshold: SHARPE_SELL },
  summary: {
    totalETFs: results.length,
    avgSharpe,
    sharpeGt1,
    sharpeGt05,
    sharpeGt0,
    beatBH,
    avgExcessAnn: avgExcess
  },
  results: results,
  portfolio: portStats,
  buyHoldPortfolio: bhPortStats,
  timestamp: new Date().toISOString()
};
fs.writeFileSync(RESULT_FILE, JSON.stringify(saveData, null, 2), 'utf8');
p('');
p('[Saved: ' + RESULT_FILE + ']');

// Save report
fs.writeFileSync(REPORT_FILE, log.join('\n'), 'utf8');
p('[Saved: ' + REPORT_FILE + ']');
