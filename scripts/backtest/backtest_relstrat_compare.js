// ============================================================
// 回测：相对强弱条件对比
// 规则A（当前）：  20日涨幅 > 沪深300涨幅
// 规则B（提议）：  20日涨幅 > 沪深300涨幅  AND  沪深300 20日涨幅 > 0
// ============================================================
var fs = require('fs');
var path = require('path');

var DATA_DIR = 'D:/QClaw_Trading/data/history';
var OUT_FILE = 'D:/QClaw_Trading/scripts/backtest/relstrat_compare_result.json';

// ── 加载K线：统一转为 [{date, close, vol}] ─────────────────────
function loadKline(code) {
  var f = path.join(DATA_DIR, code + '.json');
  if (!fs.existsSync(f)) return null;
  var raw = JSON.parse(fs.readFileSync(f, 'utf8'));
  // ETF: {code, records:[...]} 格式
  if (raw.records) {
    return raw.records.map(function(d) {
      return { date: d.date, close: parseFloat(d.close), vol: parseFloat(d.vol || 0) };
    });
  }
  // 数组格式 [{date, close, vol}, ...]
  if (Array.isArray(raw)) return raw;
  return null;
}

// ── 加载沪深300 ────────────────────────────────────────────────
function loadHS300() {
  return loadKline('sh000300'); // 直接复用，格式已统一
}

// ── 技术指标 ──────────────────────────────────────────────────
function SMA(arr, n) {
  var out = new Array(arr.length).fill(null);
  for (var i = n - 1; i < arr.length; i++) {
    var s = 0;
    for (var j = i - n + 1; j <= i; j++) s += arr[j];
    out[i] = s / n;
  }
  return out;
}
function EMA(arr, n) {
  var k = 2 / (n + 1), out = new Array(arr.length).fill(null);
  var seed = 0;
  for (var i = 0; i < n; i++) seed += arr[i];
  out[n - 1] = seed / n;
  for (var i = n; i < arr.length; i++) out[i] = arr[i] * k + out[i - 1] * (1 - k);
  return out;
}
function MACDCalc(prices) {
  var ef = EMA(prices, 12), es = EMA(prices, 26);
  var dif = new Array(prices.length).fill(null);
  for (var i = 25; i < prices.length; i++) dif[i] = ef[i] - es[i];
  var sk = 2 / 10, sig = new Array(prices.length).fill(null);
  sig[25] = dif[25];
  for (var i = 26; i < dif.length; i++) sig[i] = dif[i] * sk + sig[i - 1] * (1 - sk);
  var hist = dif.map(function(v, i) { return v == null ? null : v - (sig[i] || 0); });
  return { dif: dif, sig: sig, hist: hist };
}
function pctN(closes, n) {
  if (closes.length <= n) return null;
  return (closes[closes.length - 1] - closes[closes.length - 1 - n]) / closes[closes.length - 1 - n] * 100;
}

// ── 对某只ETF在某个历史截点计算评分和信号 ─────────────────────
function scoreAt(etfHist, bmPct20, endIdx) {
  // 构建截止到 endIdx 的价格序列（保证不回看未来）
  var C = etfHist.slice(0, endIdx + 1).map(function(d) { return d.close; });
  var V = etfHist.slice(0, endIdx + 1).map(function(d) { return d.vol; });
  if (C.length < 60) return null; // 至少需要60天数据

  var ma20 = SMA(C, 20), ma50 = SMA(C, 50);
  var macd = MACDCalc(C);
  var i = C.length - 1; // 当前（截点）
  var i1 = C.length - 2; // 前一天

  if (ma20[i] == null || ma50[i] == null) return null;

  var price = C[i], vol = V[i];
  var volAvg = V.slice(i - 19, i + 1).reduce(function(a, b) { return a + b; }, 0) / 20;
  var ma20c = ma20[i], ma20p1 = ma20[i1], ma50c = ma50[i];
  var d = macd.dif[i], d1 = macd.dif[i1], s = macd.sig[i], s1 = macd.sig[i1];
  var h = macd.hist[i], h1 = macd.hist[i1];
  var pct5 = pctN(C, 5), pct20 = pctN(C, 20);

  var aboveMa20 = price > ma20c;
  var ma20Up = ma20c >= ma20p1;
  var macdAboveZero = d > 0 && s > 0;
  var goldX = d1 <= s1 && d > s; // 金叉
  var histUp = h != null && h1 != null && h > h1;

  // ── 规则A：仅相对强弱 ─────────────────────────────
  var relA = pct20 != null && bmPct20 != null ? pct20 - bmPct20 : -999;
  // ── 规则B：相对强弱 + 沪深300正向 ──────────────────
  var bmPositive = bmPct20 != null && bmPct20 > 0;
  var relB = bmPositive && pct20 != null ? pct20 - bmPct20 : -999;

  var scoreA = 0, scoreB = 0;

  // 趋势
  if (aboveMa20) { scoreA += 1; scoreB += 1; }
  if (ma20c > ma50c) { scoreA += 1; scoreB += 1; }
  if (ma20c > ma50c && ma50c > 0) { scoreA += 2; scoreB += 2; }
  if (ma20Up) { scoreA += 1; scoreB += 1; }
  // 动量
  if (macdAboveZero) { scoreA += 1; scoreB += 1; }
  if (goldX && macdAboveZero) { scoreA += 2; scoreB += 2; }
  else if (goldX) { scoreA += 1; scoreB += 1; }
  if (histUp) { scoreA += 1; scoreB += 1; }
  // 相对强弱（规则A vs 规则B）
  if (relA > 0) scoreA += 2;
  else if (relA > -2) scoreA += 1;
  if (relB > 0) scoreB += 2;
  else if (relB > -2) scoreB += 1;
  // 成交量
  if (vol > volAvg * 1.5) { scoreA += 1; scoreB += 1; }

  // 星级
  function stars(s) { return s >= 11 ? 5 : s >= 9 ? 4 : s >= 6 ? 3 : s >= 4 ? 2 : 1; }

  // 信号：v3.4卖出=仅MA20跌破，买入=零轴上金叉+站上MA20
  // 规则A：买入条件不含"沪深300正向"
  var buyA = aboveMa20 && goldX && macdAboveZero;
  // 规则B：买入条件额外要求"沪深300 20日涨幅 > 0"
  var buyB = aboveMa20 && goldX && macdAboveZero && bmPositive;

  return {
    starsA: stars(scoreA), starsB: stars(scoreB),
    buyA: buyA, buyB: buyB,
    bmPct20: bmPct20, bmPositive: bmPositive,
    relA: relA, relB: relB,
    pct20: pct20
  };
}

// ── 主回测 ─────────────────────────────────────────────────────
function runBacktest() {
  console.log('═══════════════════════════════════════════════════════');
  console.log('  相对强弱条件回测');
  console.log('  规则A: 20日涨幅 > 沪深300涨幅');
  console.log('  规则B: 20日涨幅 > 沪深300涨幅  AND  沪深300 20日涨幅 > 0');
  console.log('═══════════════════════════════════════════════════════\n');

  var hs300 = loadHS300();
  if (!hs300 || hs300.length === 0) { console.log('❌ 沪深300数据缺失'); return; }
  console.log('>> 沪深300历史：' + hs300.length + '条，' + hs300[0].date + ' ~ ' + hs300[hs300.length - 1].date);

  // 建立日期→沪深300收盘价映射
  var hs300Map = {};
  for (var hi = 0; hi < hs300.length; hi++) hs300Map[hs300[hi].date] = hs300[hi].close;

  // 计算沪深300每日pct20（从第20天开始有值）
  var bmPct20Arr = {};
  for (var hi = 20; hi < hs300.length; hi++) {
    var pct = (hs300[hi].close - hs300[hi - 20].close) / hs300[hi - 20].close * 100;
    bmPct20Arr[hs300[hi].date] = pct;
  }

  // 扫描ETF文件
  var allFiles = fs.readdirSync(DATA_DIR).filter(function(f) { return f.endsWith('.json'); });
  var etfCodes = allFiles
    .filter(function(f) { return /^(sh|sz)/.test(f) && !/^sh000/.test(f) && !/^sz399/.test(f) && !/^sh001/.test(f); })
    .map(function(f) { return f.replace('.json', ''); });

  console.log('>> ETF数量：' + etfCodes.length + '\n');

  // 统计
  var S = {
    totalDays: 0,
    A_buy: 0, B_buy: 0,
    A_hold: 0, B_hold: 0,
    A_wait: 0, B_wait: 0,
    // 沪深300区间分布
    brackets: {
      '>5%':   { days: 0, A_buy: 0, B_buy: 0 },
      '2~5%':  { days: 0, A_buy: 0, B_buy: 0 },
      '0~2%':  { days: 0, A_buy: 0, B_buy: 0 },
      '-2~0%': { days: 0, A_buy: 0, B_buy: 0 },
      '-5~-2%': { days: 0, A_buy: 0, B_buy: 0 },
      '<-5%':  { days: 0, A_buy: 0, B_buy: 0 }
    }
  };

  // 建立每只ETF的日期→index映射（快速查找）
  function loadEtfFast(code) {
    var hist = loadKline(code);
    if (!hist) return null;
    var map = {};
    for (var i = 0; i < hist.length; i++) map[hist[i].date] = i;
    return { hist: hist, map: map };
  }

  // 遍历沪深300历史日期（从第60天起，兼容ETF的MA20需求）
  var etfCache = {};
  for (var hi = 60; hi < hs300.length; hi++) {
    var date = hs300[hi].date;
    var bmPct20 = bmPct20Arr[date];
    if (bmPct20 == null) continue;

    // 对每只ETF，检查该日期是否有数据
    for (var ei = 0; ei < etfCodes.length; ei++) {
      var code = etfCodes[ei];
      if (!etfCache[code]) etfCache[code] = loadEtfFast(code);
      var ef = etfCache[code];
      if (!ef) continue;

      var idx = ef.map[date];
      if (idx == null || idx < 60) continue; // 需要至少60天数据

      var sc = scoreAt(ef.hist, bmPct20, idx);
      if (!sc) continue;

      S.totalDays++;
      if (sc.buyA) { S.A_buy++; }
      if (sc.buyB) { S.B_buy++; }

      // 沪深300区间
      var bracket;
      if      (bmPct20 > 5)  bracket = '>5%';
      else if (bmPct20 > 2)  bracket = '2~5%';
      else if (bmPct20 > 0)  bracket = '0~2%';
      else if (bmPct20 > -2) bracket = '-2~0%';
      else if (bmPct20 > -5) bracket = '-5~-2%';
      else                   bracket = '<-5%';
      S.brackets[bracket].days++;
      if (sc.buyA) S.brackets[bracket].A_buy++;
      if (sc.buyB) S.brackets[bracket].B_buy++;
    }
  }

  // ── 输出结果 ────────────────────────────────────────────────
  var total = S.totalDays;
  console.log('\n═══════════════════════════════════════════════════════');
  console.log('  回测结果（' + etfCodes.length + '只ETF × ' + hs300.length + '天 ≈ 最大' + (etfCodes.length * (hs300.length - 60)) + '条交易日，实际有效：' + total.toLocaleString() + '）');
  console.log('═══════════════════════════════════════════════════════\n');

  console.log('【整体信号分布】');
  console.log('                   规则A（当前）   规则B（提议）   差异');
  console.log('  BUY信号        ' + pad(S.A_buy, 10) + pad(S.B_buy, 12) + (S.B_buy - S.A_buy));
  console.log('  BUY占比        ' + pad((S.A_buy / total * 100).toFixed(2) + '%', 10) + pad((S.B_buy / total * 100).toFixed(2) + '%', 12));
  console.log('  规则B损失BUY信号：' + (S.A_buy - S.B_buy) + '次，占规则A的 ' + (S.A_buy > 0 ? ((S.A_buy - S.B_buy) / S.A_buy * 100).toFixed(1) + '%' : 'N/A'));

  console.log('\n【按沪深300区间分组（核心分析）】');
  console.log('  区间              天数      规则A BUY  规则B BUY  规则B损失');
  console.log('  ───────────────────────────────────────────────────');
  var bracketNames = ['>5%', '2~5%', '0~2%', '-2~0%', '-5~-2%', '<-5%'];
  var bracketLabels = ['强势上涨 >+5%', '温和上涨 +2~5%', '小幅上涨 0~+2%', '小幅下跌 0~-2%', '温和下跌 -2~-5%', '大幅下跌 <-5%'];
  for (var bi = 0; bi < bracketNames.length; bi++) {
    var b = S.brackets[bracketNames[bi]];
    var loss = b.A_buy - b.B_buy;
    var icon = bracketNames[bi].startsWith('-') ? '🔴' : '🟢';
    console.log('  ' + icon + ' ' + pad(bracketLabels[bi], 14) + pad(b.days.toLocaleString(), 9) + pad(b.A_buy.toLocaleString(), 10) + pad(b.B_buy.toLocaleString(), 10) + (loss > 0 ? '▼' + loss : loss === 0 ? '无' : '▲' + Math.abs(loss)));
  }

  var posDays = 0, posAb = 0, posBb = 0;
  var negDays = 0, negAb = 0, negBb = 0;
  for (var bi = 0; bi < bracketNames.length; bi++) {
    var b = S.brackets[bracketNames[bi]];
    if (bracketNames[bi].startsWith('-')) { negDays += b.days; negAb += b.A_buy; negBb += b.B_buy; }
    else { posDays += b.days; posAb += b.A_buy; posBb += b.B_buy; }
  }

  console.log('\n【沪深300方向汇总】');
  console.log('  沪深300 20日涨幅 > 0（多头区间）：' + posDays.toLocaleString() + '天');
  console.log('    规则A BUY：' + posAb.toLocaleString() + '次  规则B BUY：' + posBb.toLocaleString() + '次  损失：' + (posAb - posBb));
  console.log('    ' + (posAb - posBb === 0 ? '✅ 规则B在多头区间无损失' : '⚠️ 规则B在多头区间损失' + (posAb - posBb) + '次'));
  console.log('');
  console.log('  沪深300 20日涨幅 < 0（空头区间）：' + negDays.toLocaleString() + '天');
  console.log('    规则A BUY：' + negAb.toLocaleString() + '次  规则B BUY：' + negBb.toLocaleString() + '次  过滤：' + (negAb - negBb));
  console.log('    ' + (negAb - negBb > 0 ? '✅ 规则B成功过滤' + (negAb - negBb) + '个熊市防御陷阱信号（这是好事）' : '⚠️ 熊市区间也有信号，无额外过滤效果'));

  // 结论
  var lossRate = S.A_buy > 0 ? (S.A_buy - S.B_buy) / S.A_buy * 100 : 0;
  console.log('\n═══════════════════════════════════════════════════════');
  console.log('  结论');
  console.log('═══════════════════════════════════════════════════════');
  if (lossRate < 3) {
    console.log('  ✅ 规则B可行：信号损失率仅' + lossRate.toFixed(1) + '%，在多头区间完全无损失');
  } else if (lossRate < 10) {
    console.log('  ⚠️ 规则B可接受：信号损失率' + lossRate.toFixed(1) + '%，需确认损失集中在空头区间');
  } else {
    console.log('  🔴 规则B损失过大（' + lossRate.toFixed(1) + '%），不建议采用');
  }
  console.log('');
  console.log('  建议采用混合规则：');
  console.log('    A股ETF：     20日涨幅 > 沪深300涨幅  AND  沪深300 20日涨幅 > 0');
  console.log('    QDII/商品ETF：  20日涨幅 > 0（绝对动量）');
  console.log('');

  // 保存
  var result = {
    version: 'v1.0',
    date: new Date().toISOString().slice(0, 10),
    summary: {
      totalDays: total,
      ruleA_buy: S.A_buy, ruleA_buyPct: (S.A_buy / total * 100).toFixed(2) + '%',
      ruleB_buy: S.B_buy, ruleB_buyPct: (S.B_buy / total * 100).toFixed(2) + '%',
      signalLoss: S.A_buy - S.B_buy, lossRate: lossRate.toFixed(2) + '%',
      hs300pos_days: posDays, hs300pos_Abuy: posAb, hs300pos_Bbuy: posBb,
      hs300neg_days: negDays, hs300neg_Abuy: negAb, hs300neg_Bbuy: negBb
    },
    brackets: S.brackets
  };
  fs.writeFileSync(OUT_FILE, JSON.stringify(result, null, 2), 'utf8');
  console.log('  结果已保存：' + OUT_FILE);
}

function pad(n, w) {
  n = String(n);
  return n + new Array(Math.max(1, w - n.length)).join(' ');
}

runBacktest();
