// ============================================================
// 全市场ETF信号扫描 v3.7（重写版）
// 策略：MA20+MACD共振选基策略 v3.7
// 标的池：60只 ETF（data/etf_pool.js）
// 规则：五星评分（13分）+ 分市场相对强弱 + 相关性过滤
// ============================================================

'use strict';

var path = require('path');
var fs   = require('fs');

var POOL_FILE = path.join(__dirname, '..', '..', 'data', 'etf_pool.js');
var SCRIPT_DIR = __dirname;
var POOL_FILE_LOCAL = path.join(SCRIPT_DIR, 'etf_pool.json');

var ALL_ETFS;
try {
  ALL_ETFS = JSON.parse(fs.readFileSync(POOL_FILE_LOCAL, 'utf8'));
} catch(e) {
  console.error('读取失败: ' + POOL_FILE_LOCAL + ' — ' + e.message);
  process.exit(1);
}
console.log('共加载 ' + ALL_ETFS.length + ' 只ETF\n');

// ════════════════════════════════════════════════════════════
// 一、技术指标
// ════════════════════════════════════════════════════════════

function SMA(prices, n) {
  var out = new Array(prices.length).fill(null);
  for (var i = n - 1; i < prices.length; i++) {
    var s = 0;
    for (var j = i - n + 1; j <= i; j++) s += prices[j];
    out[i] = s / n;
  }
  return out;
}

function EMA(prices, n) {
  var k  = 2 / (n + 1);
  var ef = [];
  ef[n - 1] = prices.slice(0, n).reduce(function(a, b) { return a + b; }, 0) / n;
  for (var i = n; i < prices.length; i++) {
    ef[i] = prices[i] * k + ef[i - 1] * (1 - k);
  }
  // Fill nulls for the first n-1 positions
  var out = new Array(n - 1).fill(null).concat(ef.slice(n - 1));
  return out;
}

function MACD(prices, f, s, sig) {
  f   = f  || 12;
  s   = s  || 26;
  sig = sig || 9;
  var ef = EMA(prices, f);
  var es = EMA(prices, s);
  var dif = [];
  for (var i = 0; i < prices.length; i++) {
    dif[i] = (ef[i] !== null && es[i] !== null) ? ef[i] - es[i] : null;
  }
  var sk = 2 / (sig + 1);
  var se = [];
  // Seed DEA with first valid DIF
  var firstDif = null;
  for (var di = s - 1; di < dif.length; di++) { if (dif[di] !== null) { firstDif = dif[di]; break; } }
  se[s - 1] = firstDif;
  for (var si = s; si < dif.length; si++) {
    se[si] = (dif[si] !== null) ? dif[si] * sk + se[si - 1] * (1 - sk) : null;
  }
  var hist = dif.map(function(v, i) {
    return (v !== null && se[i] !== null) ? v - se[i] : null;
  });
  return { dif: dif, sig: se, hist: hist };
}

// N日收益率（%），用日期对齐而非索引
function pctReturn(prices, data, n) {
  if (n < 1 || prices.length < n + 1) return null;
  var end   = prices.length - 1;
  var start = end - n;
  if (prices[start] > 0) {
    return (prices[end] - prices[start]) / prices[start] * 100;
  }
  return null;
}

// Pearson相关系数（基于日收益率序列）
function pearsonCorr(prices1, prices2) {
  function toReturns(arr) {
    var r = [];
    for (var i = 1; i < arr.length; i++) {
      if (arr[i] > 0 && arr[i - 1] > 0) {
        r.push((arr[i] - arr[i - 1]) / arr[i - 1]);
      }
    }
    return r;
  }
  var r1 = toReturns(prices1);
  var r2 = toReturns(prices2);
  var n  = Math.min(r1.length, r2.length, 120);
  if (n < 10) return 0;
  var s1 = r1.length - n, s2 = r2.length - n;
  var sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
  for (var i = 0; i < n; i++) {
    var x = r1[s1 + i], y = r2[s2 + i];
    sumX += x; sumY += y; sumXY += x * y; sumX2 += x * x; sumY2 += y * y;
  }
  var den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
  return den === 0 ? 0 : (n * sumXY - sumX * sumY) / den;
}

// ════════════════════════════════════════════════════════════
// 二、基准数据
// ════════════════════════════════════════════════════════════

// 主流指数基准定义
var BENCHMARKS = [
  { code: 'sh000001', name: '上证指数',  type: 'A股' },
  { code: 'sh000300', name: '沪深300',   type: 'A股' },
  { code: 'sh000905', name: '中证500',   type: 'A股' },
  { code: 'sh000852', name: '中证1000',  type: 'A股' },
  { code: 'sh000016', name: '上证50',     type: 'A股' },
  { code: 'sz399001', name: '深证成指',   type: 'A股' },
  { code: 'sz399006', name: '创业板指',   type: 'A股' },
  { code: 'sh000688', name: '科创50',    type: 'A股' },
  { code: 'hkHSI',    name: '恒生指数',   type: '港股' },
  { code: 'hkHSTECH', name: '恒生科技',  type: '港股' },
  { code: 'sz513500', name: '标普500ETF(513500)', type: '美股' },
];

// 全局基准值（分市场）
var BM = {
  'A股':   { name: '沪深300',  pct5: null, pct20: null },
  '港股':  { name: '恒生指数', pct5: null, pct20: null },
  '美股':  { name: '标普500ETF(513500)', pct5: null, pct20: null },
};

// ════════════════════════════════════════════════════════════
// 三、工具函数
// ════════════════════════════════════════════════════════════

var sleep = function(ms) { return new Promise(function(r) { setTimeout(r, ms); }); };

function txSecid(code, market) {
  return market === 'SZ' ? 'sz' + code : 'sh' + code;
}

// 判断ETF所属市场（用于确定相对强弱基准）
function etfMarket(etf) {
  if (etf.category === '商品') return '商品';
  if (etf.category === '债券') return '债券';
  if (etf.category === '跨境QDII') {
    var n = (etf.name || '') + (etf.index || '') + (etf.code || '');
    if (/港股|恒生|H股|港中小/.test(n)) return '港股';
    if (/纳指|纳斯达克|NDX|标普|SPX|道琼斯|DJ|美股/.test(n)) return '美股';
    return '其他跨境'; // 巴西、沙特、德国、日本等，无合适跨市场基准
  }
  return 'A股';
}

// ════════════════════════════════════════════════════════════
// 四、数据获取
// ════════════════════════════════════════════════════════════

// 腾讯指数日K
async function fetchIndex(code) {
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + code + ',day,,,40,qfq';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(8000) });
    var j = await r.json();
    var d = j.data && j.data[code];
    var arr = d ? (d.qfqday || d.day || []) : [];
    return arr.map(function(k) {
      return { date: k[0], close: +k[2], vol: +k[5] };
    });
  } catch(e) { return []; }
}

// 腾讯行情ETF日K
async function fetchTx(code, market) {
  var secid = txSecid(code, market);
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,180,qfq';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(10000) });
    var j = await r.json();
    var arr = j.data && j.data[secid]
      ? (j.data[secid].qfqday || j.data[secid].day || [])
      : [];
    return arr.map(function(k) {
      return { date: k[0], close: +k[2], vol: +k[5] };
    });
  } catch(e) { return []; }
}

// 东方财富ETF日K（兜底）
async function fetchEM(code, market) {
  var secid = market === 'SZ' ? '0.' + code : '1.' + code;
  var url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get' +
    '?secid=' + secid +
    '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61' +
    '&klt=101&fqt=0&beg=20200101&end=20260420&lmt=200';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(8000) });
    var j = await r.json();
    var klines = (j.data && j.data.klines) ? j.data.klines : [];
    return klines.map(function(k) {
      var p = k.split(',');
      return { date: p[0], close: +p[2], vol: +p[5] };
    });
  } catch(e) { return []; }
}

// ════════════════════════════════════════════════════════════
// 五、核心评分
// ════════════════════════════════════════════════════════════

function calcStar(data, etf) {
  if (data.length < 60) return null;

  var C = data.map(function(d) { return d.close; });
  var V = data.map(function(d) { return d.vol; });
  var i  = C.length - 1;   // 今天
  var i1 = C.length - 2;   // 昨天

  var ma20  = SMA(C, 20);
  var ma50  = SMA(C, 50);
  var ma200 = SMA(C, 200);
  var macd  = MACD(C, 12, 26, 9);

  var price  = C[i];
  var ma20c  = ma20[i];
  var ma50c  = ma50[i];
  var ma200c = ma200[i];

  if (ma20c === null) return null;

  var ma20p1 = ma20[i1] || ma20c;
  var ma50p1 = ma50[i1] || ma50c;

  var d    = macd.dif[i];
  var dP1  = macd.dif[i1];
  var s    = macd.sig[i];
  var sP1  = macd.sig[i1];
  var h    = macd.hist[i];
  var hP1  = macd.hist[i1];

  // ── 基础条件 ─────────────────────────────────
  var aboveMa20    = price > ma20c;
  var ma20Up       = ma20c > ma20p1;
  var ma50Up       = ma50c > ma50p1;
  var ma20Above50  = ma50c !== null ? ma20c > ma50c : false;
  var ma50Above200 = ma200c !== null ? ma50c > ma200c : false;
  var macdAboveZero = d !== null && s !== null && d > 0 && s > 0;
  var goldX        = dP1 !== null && sP1 !== null && dP1 <= sP1 && d > s;  // DIF上穿DEA
  var deathX       = dP1 !== null && sP1 !== null && dP1 >= sP1 && d < s;  // DIF下穿DEA
  var histRed      = h !== null && h > 0;   // 红柱
  var histGreen    = h !== null && h < 0;    // 绿柱

  var pct5  = pctReturn(C, data, 5);
  var pct20 = pctReturn(C, data, 20);

  // ── 相对强弱（v3.7：分市场基准）──────────────
  var mkt = etfMarket(etf);
  var bm  = BM[mkt] || { pct5: 0, pct20: 0 };
  var bm5  = bm.pct5  !== null ? bm.pct5  : 0;
  var bm20 = bm.pct20 !== null ? bm.pct20 : 0;

  var isAbsMom = (mkt === '商品' || mkt === '债券' || mkt === '其他跨境');

  // 基准自身是否多头（A股/港股/美股需基准本身>0才有效）
  var bmPositive = isAbsMom || (bm20 > 0);

  // 相对强弱：差值
  var relStr20 = isAbsMom ? 0 : pct20 - bm20;
  var relStr5  = isAbsMom ? 0 : pct5  - bm5;

  // ── 评分（13分制）─────────────────────────────
  var score = 0;

  // 趋势 (0-5)
  if (aboveMa20)                                             score += 1;  // 站上MA20
  if (ma20Above50)                                          score += 1;  // MA20>MA50
  if (ma20Above50 && ma50Above200)                          score += 2;  // 多头排列
  if (ma20Up)                                               score += 1;  // MA20向上

  // 动量 (0-4)
  if (goldX && macdAboveZero)                                score += 3;  // 零轴上金叉（最佳）
  else if (goldX)                                            score += 1;  // 零轴下金叉
  if (histRed)                                               score += 1;  // 红柱持续

  // 相对强弱 (0-3) — 美股用 >= 基准涨幅，其余用 > 基准涨幅
  if (isAbsMom) {
    if (pct20 !== null && pct20 > 0 && bmPositive)         score += 2;  // 绝对正动量
    if (pct5  !== null && pct5  > 0 && bmPositive)         score += 1;  // 短期正动量
  } else if (mkt === '美股') {
    if (relStr20 >= 0 && bmPositive)                         score += 2;  // 跑平/跑赢标普500
    if (relStr5  >= 0 && bmPositive)                         score += 1;
  } else {
    if (relStr20 > 0 && bmPositive)                          score += 2;  // 跑赢基准20日
    if (relStr5  > 0 && bmPositive)                          score += 1;  // 跑赢基准5日
  }

  // 成交量 (0-1)
  var volAvg = V.slice(i - 19, i + 1).reduce(function(a, b) { return a + b; }, 0) / 20;
  if (V[i] > volAvg * 1.5)                                   score += 1;  // 放量1.5倍

  // ── 星级映射 ────────────────────────────────
  var stars = score >= 10 ? 5 : score >= 8 ? 4 : score >= 6 ? 3 : score >= 4 ? 2 : 1;

  // ── 信号分类（v3.7：买入条件收紧）────────────
  // 核心原则：BUY = above MA20 + MA20向上 + 相对强弱达标
  var relOk = isAbsMom ? (pct20 > 0) : (relStr20 > 0 && bmPositive);
  var signal, tag;
  if (!aboveMa20) {
    signal = 'WAIT'; tag = '跌破MA20(等待)';
  } else if (!ma20Up) {
    signal = 'HOLD'; tag = 'MA20向下(观望)';
  } else if (goldX && macdAboveZero && relOk) {
    signal = 'BUY'; tag = '零轴上金叉(买入)';
  } else if (goldX && relOk) {
    signal = 'BUY'; tag = 'MACD金叉(买入)';
  } else if (macdAboveZero && histRed && relOk) {
    signal = 'BUY'; tag = '零轴上方健康(买入)';
  } else if (macdAboveZero && histRed) {
    signal = 'HOLD'; tag = '零轴上方但未跑赢基准(持股)';
  } else if (macdAboveZero) {
    signal = 'HOLD'; tag = '零轴上方持股';
  } else if (histRed) {
    signal = 'HOLD'; tag = '趋势向好持股';
  } else {
    signal = 'HOLD'; tag = 'MACD弱势持股';
  }

  // ── 卖出诊断（仅MA20跌破 + 5%止损）─────────
  var sellSignal = !aboveMa20;  // 跌破MA20即触发卖出

  return {
    etf:        etf,
    date:       data[i].date,
    price:      price,
    ma20:       ma20c,
    ma20Dir:    ma20Up ? '↑' : '↓',
    ma50:       ma50c,
    zone:       macdAboveZero ? '零轴上' : '零轴下',
    pct5:       pct5,
    pct20:      pct20,
    relStr20:   isAbsMom ? (pct20 > 0 ? '正' : '负') : (relStr20 > 0 ? '+' + relStr20.toFixed(1) + '%' : relStr20.toFixed(1) + '%'),
    score:      score,
    stars:      stars,
    signal:     signal,
    tag:        tag,
    mkt:        mkt,
    bmName:     isAbsMom ? '绝对动量' : bm.name,
    bm20:       bm20,
    sellSignal: sellSignal,
    // 相关性计算用：收盘价序列（最近120天）
    corrData:   C.slice(-120),
  };
}

// ════════════════════════════════════════════════════════════
// 六、相关性过滤（贪心算法，maxCorr ≤ 0.70）
// ════════════════════════════════════════════════════════════

function filterByCorrelation(buys) {
  if (buys.length <= 1) return buys.map(function(r) { r.filtered = false; return r; });

  buys.sort(function(a, b) {
    if (b.stars !== a.stars) return b.stars - a.stars;
    return b.score - a.score;
  });

  var selected = [];
  for (var i = 0; i < buys.length; i++) {
    var candidate = buys[i];
    var maxCorr = 0;
    for (var j = 0; j < selected.length; j++) {
      var r = pearsonCorr(selected[j].corrData, candidate.corrData);
      if (r > maxCorr) maxCorr = r;
    }
    if (maxCorr <= 0.70) {
      candidate.maxCorr   = maxCorr;
      candidate.filtered  = false;
      selected.push(candidate);
    } else {
      candidate.maxCorr   = maxCorr;
      candidate.filtered  = true;
    }
  }
  return buys; // 返回全部（含filtered标记）
}

// ════════════════════════════════════════════════════════════
// 七、输出格式化
// ════════════════════════════════════════════════════════════

function pad(s, n) {
  s = String(s === null || s === undefined ? '--' : s);
  while (s.length < n) s += ' ';
  return s;
}

function fmt(n, decimals) {
  if (n === null || n === undefined) return '--';
  return n.toFixed(decimals) + '%';
}

function printEtfRow(r, corrNote) {
  corrNote = corrNote || '';
  console.log(
    '  ' + pad(r.etf.category, 10) +
    pad(r.etf.name, 14) +
    pad(r.etf.code, 8) +
    pad('⭐'.repeat(r.stars), 6) +
    pad(r.price.toFixed(3), 8) +
    pad(r.ma20.toFixed(3), 7) +
    pad(r.ma20Dir, 3) +
    pad(r.zone, 5) +
    pad('5日' + fmt(r.pct5, 1), 9) +
    pad('20日' + fmt(r.pct20, 1), 11) +
    pad('基准:' + r.relStr20, 12) +
    '  ' + r.tag +
    corrNote
  );
}

// ════════════════════════════════════════════════════════════
// 八、主程序
// ════════════════════════════════════════════════════════════

async function main() {
  console.log('═══════════════════════════════════════════════════');
  console.log('  全市场ETF信号扫描  v3.7  |  ' + ALL_ETFS.length + '只  |  MA20+MACD共振策略');
  console.log('═══════════════════════════════════════════════════\n');

  // ── Step 1：获取分市场基准 ────────────────────
  console.log('>> 获取市场基准...');
  for (var bi = 0; bi < BENCHMARKS.length; bi++) {
    var b    = BENCHMARKS[bi];
    var data = await fetchIndex(b.code);
    await sleep(180);
    if (data.length < 10) { console.log('  ' + b.name + ': 数据不足'); continue; }
    var C    = data.map(function(d) { return d.close; });
    var pct5  = pctReturn(C, data, 5);
    var pct20 = pctReturn(C, data, 20);
    // 存入对应市场
    if (BM[b.type]) {
      BM[b.type].pct5  = pct5;
      BM[b.type].pct20 = pct20;
    }
    console.log('  ' + pad(b.name, 10) + ' 5日' + fmt(pct5, 2) + '  20日' + fmt(pct20, 2));
  }
  console.log('');

  // 打印基准汇总
  console.log('>> 相对强弱基准（v3.7分市场）：');
  for (var mk in BM) {
    var bm = BM[mk];
    console.log('  ' + mk + ' → ' + bm.name + '（20日' + fmt(bm.pct20, 2) + '，5日' + fmt(bm.pct5, 2) + '）');
  }
  console.log('');

  // ── Step 2：扫描所有ETF ───────────────────────
  console.log('>> 扫描ETF信号...');
  var results = [];
  for (var i = 0; i < ALL_ETFS.length; i++) {
    var etf    = ALL_ETFS[i];
    var suffix = '[' + (i + 1) + '/' + ALL_ETFS.length + ']';
    process.stdout.write(suffix + ' ' + etf.name + '(' + etf.code + ')... ');

    var data = await fetchTx(etf.code, etf.market);
    if (data.length < 60) {
      await sleep(350);
      data = await fetchEM(etf.code, etf.market);
    }
    await sleep(200);

    if (data.length < 60) {
      console.log('FAIL（仅' + data.length + '条）');
      results.push({ etf: etf, signal: 'FAIL', dataLen: data.length });
      continue;
    }

    var r = calcStar(data, etf);
    if (!r) {
      console.log('ERROR（指标计算失败）');
      results.push({ etf: etf, signal: 'FAIL', reason: 'calc' });
      continue;
    }

    results.push(r);
    var sigFlag = r.signal === 'BUY' ? 'BUY' : r.signal === 'HOLD' ? 'HOLD' : 'WAIT';
    console.log(
      sigFlag + ' ' + '⭐'.repeat(r.stars) +
      '  ' + r.date +
      '  MA20' + r.ma20Dir +
      '  ' + r.zone +
      '  ' + fmt(r.pct20, 1) +
      '  (' + r.mkt + ')'
    );
  }
  console.log('');

  // ── Step 3：信号统计 ──────────────────────────
  var okResults = results.filter(function(r) { return r.signal !== 'FAIL'; });
  var buys  = okResults.filter(function(r) { return r.signal === 'BUY'; });
  var holds = okResults.filter(function(r) { return r.signal === 'HOLD'; });
  var waits = okResults.filter(function(r) { return r.signal === 'WAIT'; });
  var fails = results.filter(function(r) { return r.signal === 'FAIL'; });

  console.log('═══════════════════════════════════════════════════');
  console.log('  信号统计  |  共' + okResults.length + '只有效  |  v3.7');
  console.log('═══════════════════════════════════════════════════');
  console.log('  BUY=' + buys.length + '  HOLD=' + holds.length + '  WAIT=' + waits.length + '  FAIL=' + fails.length + '\n');

  // ── Step 4：相关性过滤（仅针对BUY候选）─────────
  var allBuys = buys.slice();
  var filtered = filterByCorrelation(allBuys);
  var passed  = filtered.filter(function(r) { return !r.filtered; });
  var rejected = filtered.filter(function(r) { return r.filtered; });

  console.log('>> 相关性过滤（maxCorr ≤ 0.70）：');
  console.log('  BUY候选=' + allBuys.length + '  →  通过=' + passed.length + '  排除=' + rejected.length + '\n');

  // ── Step 5：输出结果 ───────────────────────────
  var header = '  ' + pad('类别', 10) + pad('名称', 14) + pad('代码', 8) +
    pad('星级', 6) + pad('收盘', 8) + pad('MA20', 7) +
    pad('方向', 3) + pad('零轴', 5) + pad('5日%', 9) +
    pad('20日%', 11) + pad('相对基准', 12) + '  信号';

  if (passed.length > 0) {
    console.log('───────────────────────────────────────────────────');
    console.log('>> BUY（' + passed.length + '只，已通过相关性过滤）');
    console.log(header);
    passed.forEach(function(r) {
      var note = r.maxCorr > 0 ? '  ↔ maxCorr=' + r.maxCorr.toFixed(2) : '';
      printEtfRow(r, note);
    });
    console.log('');
  }

  if (rejected.length > 0) {
    console.log('───────────────────────────────────────────────────');
    console.log('>> BUY-FILTERED（' + rejected.length + '只，相关性>0.70被排除）');
    console.log(header);
    rejected.forEach(function(r) {
      printEtfRow(r, '  [corr=' + r.maxCorr.toFixed(2) + ']');
    });
    console.log('');
  }

  if (holds.length > 0) {
    holds.sort(function(a, b) {
      if (b.stars !== a.stars) return b.stars - a.stars;
      return b.score - a.score;
    });
    console.log('───────────────────────────────────────────────────');
    console.log('>> HOLD（' + holds.length + '只，持股观望）');
    console.log(header);
    holds.forEach(function(r) { printEtfRow(r); });
    console.log('');
  }

  if (waits.length > 0) {
    var byCat = {};
    waits.forEach(function(r) {
      if (!byCat[r.etf.category]) byCat[r.etf.category] = [];
      byCat[r.etf.category].push(r.etf.name + '(' + r.etf.code + ')');
    });
    console.log('───────────────────────────────────────────────────');
    console.log('>> WAIT（' + waits.length + '只，等待信号）');
    for (var cat in byCat) {
      console.log('  [' + cat + '] ' + byCat[cat].join('、'));
    }
    console.log('');
  }

  if (fails.length > 0) {
    console.log('───────────────────────────────────────────────────');
    console.log('>> FAIL（' + fails.length + '只，数据获取失败）');
    fails.forEach(function(r) {
      console.log('  ' + r.etf.name + '(' + r.etf.code + ')' +
        (r.dataLen !== undefined ? ' — 仅' + r.dataLen + '条数据' : ''));
    });
    console.log('');
  }

  // ── Step 6：打印分市场基准汇总 ─────────────────
  console.log('═══════════════════════════════════════════════════');
  console.log('  市场基准  |  v3.7分市场相对强弱');
  console.log('═══════════════════════════════════════════════════');
  for (var mk2 in BM) {
    var bm2 = BM[mk2];
    var status = bm2.pct20 !== null
      ? (bm2.pct20 > 0 ? '🟢 多头区间' : '🔴 空头区间')
      : '⚪ 未获取';
    console.log('  ' + pad(mk2, 6) + pad(bm2.name, 12) + ' 5日' + fmt(bm2.pct5, 2) + '  20日' + fmt(bm2.pct20, 2) + '  ' + status);
  }
  console.log('');
}

main().catch(function(e) { console.error('Fatal error:', e); process.exit(1); });
