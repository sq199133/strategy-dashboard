// ============================================================
// 全市场ETF信号扫描 v3.9（重写版）
// 策略：MA20+MACD共振选基策略 v3.9
// 标的池：91只 ETF（etf_pool.json v5.1）
// 规则：五星评分（13分）+ 分市场相对强弱 + 追高过滤 + 相关性过滤
// v3.9 新增：港股恒生科技20日>0检查、追高过滤(BIAS20/短期涨幅/连涨)、黄金价差预警
// ============================================================

'use strict';

var path = require('path');
var fs   = require('fs');

var SCRIPT_DIR = __dirname;
var POOL_FILE_LOCAL = path.join(SCRIPT_DIR, 'etf_pool.json');

var ALL_ETFS;
try {
  ALL_ETFS = JSON.parse(fs.readFileSync(POOL_FILE_LOCAL, 'utf8'));
} catch(e) {
  console.error('读取失败: ' + POOL_FILE_LOCAL + ' — ' + e.message);
  process.exit(1);
}
console.log('共加载 ' + ALL_ETFS.length + ' 只ETF (v5.1)\n');

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

function pctReturn(prices, data, n) {
  if (n < 1 || prices.length < n + 1) return null;
  var end   = prices.length - 1;
  var start = end - n;
  if (prices[start] > 0) {
    return (prices[end] - prices[start]) / prices[start] * 100;
  }
  return null;
}

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

var BM = {
  'A股':   { name: '沪深300',  pct5: null, pct20: null },
  '港股':  { name: '恒生指数', pct5: null, pct20: null },
  '美股':  { name: '标普500ETF(513500)', pct5: null, pct20: null },
};

// v3.9新增：港股需额外检查恒生科技
var BM_HKTECH = { name: '恒生科技', pct5: null, pct20: null };

// ════════════════════════════════════════════════════════════
// 三、工具函数
// ════════════════════════════════════════════════════════════

var sleep = function(ms) { return new Promise(function(r) { setTimeout(r, ms); }); };

function txSecid(code, market) {
  return market === 'SZ' ? 'sz' + code : 'sh' + code;
}

// v5.1分类体系 → 市场归属
function etfMarket(etf) {
  var cat = etf.category || '';
  var idx = etf.index || '';
  var nm  = etf.name || '';

  // 商品/资源类
  if (cat === '商品/资源') return '商品';

  // 公用事业（电力等）→ A股
  // 农业 → A股
  // 地产基建 → A股
  // 传媒娱乐 → A股
  // 高端制造 → A股
  // 金融 → A股
  // 消费 → A股
  // 医药 → A股
  // 新能源 → A股
  // 科技 → A股
  // 策略指数 → A股
  // 宽基指数 → A股

  // 跨境QDII → 按名称/指数细分
  if (cat === '跨境QDII') {
    if (/港股|恒生|H股|港中小|恒生科技|恒生生物|恒生医疗|恒生互联网|港股通|中概/.test(nm + idx)) return '港股';
    if (/纳指|纳斯达克|NDX|标普|SPX|道琼斯|DJ|美股/.test(nm + idx)) return '美股';
    return '其他跨境';  // 东南亚/德国/法国/巴西/沙特等
  }

  return 'A股';
}

// ════════════════════════════════════════════════════════════
// 四、数据获取
// ════════════════════════════════════════════════════════════

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

async function fetchEM(code, market) {
  var secid = market === 'SZ' ? '0.' + code : '1.' + code;
  var url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get' +
    '?secid=' + secid +
    '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61' +
    '&klt=101&fqt=0&beg=20200101&end=20500101&lmt=200';
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
// 五、追高过滤（v3.8新增，v3.9整合）
// ════════════════════════════════════════════════════════════

function calcChaseFilter(prices, data) {
  if (prices.length < 5) return { yellowCount: 0, redLine: false, details: [], bias20: null, pct3d: null, pct5d: null, consecUp: 0 };

  var i = prices.length - 1;
  var ma20 = SMA(prices, 20);
  var ma20c = ma20[i];

  // BIAS20
  var bias20 = (ma20c !== null && ma20c > 0) ? (prices[i] - ma20c) / ma20c * 100 : null;

  // 3日涨幅
  var pct3d = (prices.length >= 4 && prices[i-3] > 0) ? (prices[i] - prices[i-3]) / prices[i-3] * 100 : null;

  // 5日涨幅
  var pct5d = (prices.length >= 6 && prices[i-5] > 0) ? (prices[i] - prices[i-5]) / prices[i-5] * 100 : null;

  // 连涨天数
  var consecUp = 0;
  for (var j = i; j > 0; j--) {
    if (prices[j] > prices[j-1]) consecUp++;
    else break;
  }

  var yellowCount = 0;
  var redLine = false;
  var details = [];

  // 黄线
  if (bias20 !== null && bias20 > 5 && bias20 <= 8)  { yellowCount++; details.push('Y1:BIAS20=' + bias20.toFixed(1) + '%'); }
  if (pct3d !== null && pct3d > 5 && pct3d <= 10)      { yellowCount++; details.push('Y2:3日涨' + pct3d.toFixed(1) + '%'); }
  if (pct5d !== null && pct5d > 10 && pct5d <= 15)     { yellowCount++; details.push('Y3:5日涨' + pct5d.toFixed(1) + '%'); }
  if (consecUp >= 5 && consecUp <= 7)                   { yellowCount++; details.push('Y4:连涨' + consecUp + '天'); }

  // 红线
  if (bias20 !== null && bias20 > 8)                     { redLine = true; details.push('R1:BIAS20=' + bias20.toFixed(1) + '%>8%'); }
  if (pct3d !== null && pct3d > 10)                       { redLine = true; details.push('R2:3日涨' + pct3d.toFixed(1) + '%>10%'); }
  if (pct5d !== null && pct5d > 15)                       { redLine = true; details.push('R3:5日涨' + pct5d.toFixed(1) + '%>15%'); }
  if (consecUp >= 8)                                      { redLine = true; details.push('R4:连涨' + consecUp + '天>=8'); }
  if (yellowCount >= 3)                                   { redLine = true; details.push('R5:黄线叠加' + yellowCount + '>=3'); }

  return { yellowCount: yellowCount, redLine: redLine, details: details, bias20: bias20, pct3d: pct3d, pct5d: pct5d, consecUp: consecUp };
}

// ════════════════════════════════════════════════════════════
// 六、核心评分
// ════════════════════════════════════════════════════════════

function calcStar(data, etf) {
  if (data.length < 60) return null;

  var C = data.map(function(d) { return d.close; });
  var V = data.map(function(d) { return d.vol; });
  var i  = C.length - 1;
  var i1 = C.length - 2;

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
  var ma50Up       = ma50c !== null ? ma50c > ma50p1 : false;
  var ma20Above50  = ma50c !== null ? ma20c > ma50c : false;
  var ma50Above200 = ma200c !== null ? ma50c > ma200c : false;
  var macdAboveZero = d !== null && s !== null && d > 0 && s > 0;
  var goldX        = dP1 !== null && sP1 !== null && dP1 <= sP1 && d > s;
  var histRed      = h !== null && h > 0;

  var pct5  = pctReturn(C, data, 5);
  var pct20 = pctReturn(C, data, 20);

  // ── 相对强弱（v3.9：分市场基准+港股恒生科技检查）──
  var mkt = etfMarket(etf);
  var bm  = BM[mkt] || { pct5: 0, pct20: 0 };
  var bm5  = bm.pct5  !== null ? bm.pct5  : 0;
  var bm20 = bm.pct20 !== null ? bm.pct20 : 0;

  var isAbsMom = (mkt === '商品' || mkt === '其他跨境');
  var bmPositive = isAbsMom || (bm20 > 0);

  // v3.9：港股ETF需恒生科技20日>0
  var hkTechPositive = true;
  if (mkt === '港股') {
    hkTechPositive = BM_HKTECH.pct20 !== null ? BM_HKTECH.pct20 > 0 : true;
    bmPositive = bmPositive && hkTechPositive;
  }

  var relStr20 = isAbsMom ? 0 : pct20 - bm20;
  var relStr5  = isAbsMom ? 0 : pct5  - bm5;

  // ── 评分（13分制）─────────────────────────────
  var score = 0;

  // 趋势 (0-5)
  if (aboveMa20)                                           score += 1;
  if (ma20Above50)                                        score += 1;
  if (ma20Above50 && ma50Above200)                        score += 2;
  if (ma20Up)                                             score += 1;

  // 动量 (0-4)
  if (goldX && macdAboveZero)                             score += 3;
  else if (goldX)                                         score += 1;
  if (histRed)                                            score += 1;

  // 相对强弱 (0-3)
  if (isAbsMom) {
    if (pct20 !== null && pct20 > 0 && bmPositive)      score += 2;
    if (pct5  !== null && pct5  > 0 && bmPositive)      score += 1;
  } else if (mkt === '美股') {
    if (relStr20 >= 0 && bmPositive)                     score += 2;
    if (relStr5  >= 0 && bmPositive)                    score += 1;
  } else {
    if (relStr20 > 0 && bmPositive)                      score += 2;
    if (relStr5  > 0 && bmPositive)                      score += 1;
  }

  // 成交量 (0-1)
  var volAvg = V.slice(i - 19, i + 1).reduce(function(a, b) { return a + b; }, 0) / 20;
  if (V[i] > volAvg * 1.5)                               score += 1;

  // ── 追高过滤（v3.9）────────────────────────
  var chase = calcChaseFilter(C, data);
  if (chase.redLine) {
    score = -1; // 红线禁买
  } else {
    score = Math.max(0, score - chase.yellowCount); // 黄线扣分
  }

  // ── 星级映射 ─────────────────────────────
  var stars = score < 0 ? -1 : (score >= 10 ? 5 : score >= 8 ? 4 : score >= 6 ? 3 : score >= 4 ? 2 : 1);

  // ── v4.0 夏普优化：波动率过滤 ───────────────
  // 计算20日年化波动率（用于风险调整）
  var vol20 = 0;
  if (C.length >= 22) {
    var rets = [];
    for (var vi = C.length - 21; vi < C.length; vi++) {
      if (C[vi] > 0 && C[vi - 1] > 0) rets.push((C[vi] - C[vi - 1]) / C[vi - 1]);
    }
    if (rets.length > 5) {
      var mean = rets.reduce(function(a, b) { return a + b; }, 0) / rets.length;
      var varSum = rets.reduce(function(a, b) { return a + (b - mean) * (b - mean); }, 0);
      vol20 = Math.sqrt(varSum / rets.length) * Math.sqrt(242); // 年化
    }
  }
  // 波动率过高的标的降低星级（年化>50%则扣1星，>80%则扣2星）
  var volStars = 0;
  if (vol20 > 0.8) volStars = -2;
  else if (vol20 > 0.5) volStars = -1;
  stars = Math.max(stars < 0 ? -1 : 1, stars + volStars);
  score = Math.max(0, score + volStars * 2); // score也对应调整

  // ── 信号分类（v4.0）─────────────────────
  var signal, tag;
  var starOk = stars >= 4; // ⭐⭐⭐⭐以上才可买入
  var chaseOk = !chase.redLine; // 无红线才可买入

  if (!aboveMa20) {
    signal = 'WAIT'; tag = '跌破MA20(等待)';
  } else if (chase.redLine) {
    signal = 'WATCH'; tag = '🔴追高红线(观察池)';
  } else if (score < 0) {
    signal = 'WATCH'; tag = '🔴波动率超标';
  } else if (!ma20Up) {
    signal = 'HOLD'; tag = 'MA20向下(观望)';
  } else if (goldX && macdAboveZero && bmPositive && starOk && chaseOk) {
    signal = 'BUY'; tag = '零轴上金叉 ⭐⭐⭐⭐+';
  } else if (goldX && bmPositive && starOk && chaseOk) {
    signal = 'BUY'; tag = 'MACD金叉 ⭐⭐⭐⭐+';
  } else if (macdAboveZero && histRed && bmPositive && starOk && chaseOk) {
    signal = 'BUY'; tag = '零轴上方健康 ⭐⭐⭐⭐+';
  } else if (macdAboveZero && histRed) {
    signal = 'HOLD'; tag = '零轴上方但未跑赢基准';
  } else if (macdAboveZero) {
    signal = 'HOLD'; tag = '零轴上方持股';
  } else if (histRed) {
    signal = 'HOLD'; tag = '趋势向好持股';
  } else {
    signal = 'HOLD'; tag = 'MACD弱势持股';
  }

  // ── 卖出诊断 ──────────────────────────────
  var sellSignal = !aboveMa20;

  // ── 黄金价差预警（v3.9）────────────────────
  var goldWarning = '';
  if (/黄金/.test(etf.name + (etf.index || '')) && aboveMa20) {
    var gap = (price - ma20c) / ma20c * 100;
    if (gap < 0.5) {
      goldWarning = '🔴黄金价差<0.5%! 下一交易日开盘立即卖出!';
    } else if (gap < 1) {
      goldWarning = '⚠️黄金价差<1%, 每日必须重点报告!';
    }
  }

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
    score:      score < 0 ? 0 : score,
    rawScore:   score,
    stars:      stars,
    signal:     signal,
    tag:        tag,
    mkt:        mkt,
    bmName:     isAbsMom ? '绝对动量' : bm.name,
    bm20:       bm20,
    sellSignal: sellSignal,
    goldWarning: goldWarning,
    chase:      chase,
    hkTechOk:   mkt === '港股' ? hkTechPositive : null,
    corrData:   C.slice(-120),
  };
}

// ════════════════════════════════════════════════════════════
// 七、相关性过滤
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
  return buys;
}

// ════════════════════════════════════════════════════════════
// 八、输出格式化
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
  var chaseNote = r.chase.redLine ? ' [🔴红线]' : (r.chase.yellowCount > 0 ? ' [🟡黄线-' + r.chase.yellowCount + ']' : '');
  var goldNote = r.goldWarning ? ' ' + r.goldWarning : '';
  console.log(
    '  ' + pad(r.etf.category, 10) +
    pad(r.etf.name, 16) +
    pad(r.etf.code, 8) +
    pad(r.stars < 0 ? '红线' : '⭐'.repeat(r.stars), 6) +
    pad(r.price.toFixed(3), 8) +
    pad(r.ma20.toFixed(3), 7) +
    pad(r.ma20Dir, 3) +
    pad(r.zone, 5) +
    pad('5日' + fmt(r.pct5, 1), 9) +
    pad('20日' + fmt(r.pct20, 1), 11) +
    pad('基准:' + r.relStr20, 12) +
    '  ' + r.tag +
    chaseNote +
    goldNote +
    corrNote
  );
}

// ════════════════════════════════════════════════════════════
// 九、主程序
// ════════════════════════════════════════════════════════════

async function main() {
  console.log('═══════════════════════════════════════════════════');
  console.log('  全市场ETF信号扫描  v3.9  |  ' + ALL_ETFS.length + '只  |  MA20+MACD+追高过滤');
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
    if (BM[b.type]) {
      BM[b.type].pct5  = pct5;
      BM[b.type].pct20 = pct20;
    }
    // v3.9: 恒生科技单独存储
    if (b.code === 'hkHSTECH') {
      BM_HKTECH.pct5  = pct5;
      BM_HKTECH.pct20 = pct20;
    }
    console.log('  ' + pad(b.name, 10) + ' 5日' + fmt(pct5, 2) + '  20日' + fmt(pct20, 2));
  }
  console.log('');

  console.log('>> 相对强弱基准（v3.9分市场）：');
  for (var mk in BM) {
    var bm = BM[mk];
    console.log('  ' + mk + ' → ' + bm.name + '（20日' + fmt(bm.pct20, 2) + '，5日' + fmt(bm.pct5, 2) + '）');
  }
  console.log('  港股附加 → ' + BM_HKTECH.name + '（20日' + fmt(BM_HKTECH.pct20, 2) + '，5日' + fmt(BM_HKTECH.pct5, 2) + '）' + (BM_HKTECH.pct20 > 0 ? ' ✅' : ' ❌弱势'));
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
    var sigFlag = r.signal === 'BUY' ? 'BUY' : r.signal === 'WATCH' ? '🔴WATCH' : r.signal === 'HOLD' ? 'HOLD' : 'WAIT';
    console.log(
      sigFlag + ' ' + (r.stars < 0 ? '红线' : '⭐'.repeat(r.stars)) +
      '  ' + r.date +
      '  MA20' + r.ma20Dir +
      '  ' + r.zone +
      '  ' + fmt(r.pct20, 1) +
      '  (' + r.mkt + ')' +
      (r.chase.redLine ? ' 🔴追高' : '') +
      (r.goldWarning ? ' ⚠️黄金' : '')
    );
  }
  console.log('');

  // ── Step 3：信号统计 ──────────────────────────
  var okResults = results.filter(function(r) { return r.signal !== 'FAIL'; });
  var buys  = okResults.filter(function(r) { return r.signal === 'BUY'; });
  var watches = okResults.filter(function(r) { return r.signal === 'WATCH'; });
  var holds = okResults.filter(function(r) { return r.signal === 'HOLD'; });
  var waits = okResults.filter(function(r) { return r.signal === 'WAIT'; });
  var fails = results.filter(function(r) { return r.signal === 'FAIL'; });

  console.log('═══════════════════════════════════════════════════');
  console.log('  信号统计  |  共' + okResults.length + '只有效  |  v3.9');
  console.log('═══════════════════════════════════════════════════');
  console.log('  BUY=' + buys.length + '  WATCH=' + watches.length + '  HOLD=' + holds.length + '  WAIT=' + waits.length + '  FAIL=' + fails.length + '\n');

  // ── Step 4：相关性过滤 ─────────────────────────
  var allBuys = buys.slice();
  var filtered = filterByCorrelation(allBuys);
  var passed  = filtered.filter(function(r) { return !r.filtered; });
  var rejected = filtered.filter(function(r) { return r.filtered; });

  console.log('>> 相关性过滤（maxCorr ≤ 0.70）：');
  console.log('  BUY候选=' + allBuys.length + '  →  通过=' + passed.length + '  排除=' + rejected.length + '\n');

  // ── Step 5：输出结果 ───────────────────────────
  var header = '  ' + pad('类别', 10) + pad('名称', 16) + pad('代码', 8) +
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

  if (watches.length > 0) {
    console.log('───────────────────────────────────────────────────');
    console.log('>> WATCH/观察池（' + watches.length + '只，追高红线禁买）');
    console.log(header);
    watches.forEach(function(r) { printEtfRow(r); });
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

  // ── Step 6：市场基准汇总 ──────────────────────
  console.log('═══════════════════════════════════════════════════');
  console.log('  市场基准  |  v3.9分市场相对强弱');
  console.log('═══════════════════════════════════════════════════');
  for (var mk2 in BM) {
    var bm2 = BM[mk2];
    var status = bm2.pct20 !== null
      ? (bm2.pct20 > 0 ? '🟢 多头区间' : '🔴 空头区间')
      : '⚪ 未获取';
    console.log('  ' + pad(mk2, 6) + pad(bm2.name, 12) + ' 5日' + fmt(bm2.pct5, 2) + '  20日' + fmt(bm2.pct20, 2) + '  ' + status);
  }
  console.log('  ' + pad('港股+', 6) + pad(BM_HKTECH.name, 12) + ' 5日' + fmt(BM_HKTECH.pct5, 2) + '  20日' + fmt(BM_HKTECH.pct20, 2) + '  ' + (BM_HKTECH.pct20 > 0 ? '🟢' : '🔴弱势'));
  console.log('');
}

main().catch(function(e) { console.error('Fatal error:', e); process.exit(1); });
