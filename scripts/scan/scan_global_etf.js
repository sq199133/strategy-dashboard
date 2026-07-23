// ============================================================
// ============================================================
// 全市场ETF信号扫描 v3.4
// 策略：MA20+MACD共振 · 五星评分 · 相关性过滤
// CommonJS — 运行: node scan_global_etf.js
//
// v3.4 修复：
// - P0: pearsonCorr 改用日收益率（原用收盘价，相关性虚高）
// - P0: 删除 MACD死叉/连续绿柱 卖出触发（回测证明劣于仅用MA20跌破）
// - P0: 删除 histGreen3 卖出判断（与MACD死叉100%重叠）
// ============================================================

var path = require('path');
var fs   = require('fs');

var SCRIPT_DIR = __dirname;
var ALL_ETFS = JSON.parse(fs.readFileSync(path.join(SCRIPT_DIR, 'etf_pool.json'), 'utf8'));
console.log('共加载 ' + ALL_ETFS.length + ' 只ETF\n');

// ── 全局基准 ──────────────────────────────────────
var globalBenchmarkPct20 = null;   // 创业板指20日涨幅（基准）
var globalBenchmarkPct5  = null;
function setBenchmark(p20, p5) {
  globalBenchmarkPct20 = p20;
  globalBenchmarkPct5  = p5;
}

function sleep(ms) { return new Promise(function(r){ setTimeout(r, ms); }); }

// ── 行情代码转换 ──────────────────────────────────
function txSecid(code, market) {
  return market === 'SZ' ? 'sz' + code : 'sh' + code;
}

// ── 主流指数基准 ──────────────────────────────────
var BENCHMARKS = [
  { code:'sh000001', name:'上证指数',   type:'A股' },
  { code:'sz399006', name:'创业板指',   type:'A股' },
  { code:'sh000300', name:'沪深300',   type:'A股' },
  { code:'sh000688', name:'科创50',     type:'A股' },
  { code:'sz399001', name:'深证成指',   type:'A股' },
  { code:'sh000016', name:'上证50',     type:'A股' },
  { code:'sh000905', name:'中证500',   type:'A股' },
  { code:'sh000852', name:'中证1000',  type:'A股' },
  { code:'hkHSI',    name:'恒生指数',   type:'港股' },
  { code:'hkHSTECH', name:'恒生科技',   type:'港股' },
  { code:'usNDX100', name:'纳斯达克100',type:'美股' },
  { code:'usSPX',    name:'标普500',    type:'美股' },
];

// ── 数据源：腾讯指数日K ──────────────────────────
async function fetchIndex(code) {
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + code + ',day,,,30,qfq';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(8000) });
    var j = await r.json();
    var d = j.data && j.data[code];
    var arr = d ? (d.qfqday || d.day || []) : [];
    return arr.map(function(k) {
      return { date:k[0], open:+k[1], close:+k[2], high:+k[3], low:+k[4], vol:+k[5] };
    });
  } catch(e) { return []; }
}

// ── 数据源1：腾讯行情ETF日K ──────────────────────
async function fetchTx(code, market) {
  var secid = txSecid(code, market);
  var url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,150,qfq';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(10000) });
    var j = await r.json();
    var arr = j.data && j.data[secid]
      ? (j.data[secid].qfqday || j.data[secid].day || [])
      : [];
    return arr.map(function(k) {
      return { date:k[0], open:+k[1], close:+k[2], high:+k[3], low:+k[4], vol:+k[5] };
    });
  } catch(e) { return []; }
}

// ── 数据源2：东方财富ETF日K（兜底）───────────────
async function fetchEM(code, market) {
  var secid = market === 'SZ' ? '0.' + code : '1.' + code;
  var url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get' +
    '?secid=' + secid +
    '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61' +
    '&klt=101&fqt=0&beg=20200101&end=20260416&lmt=200';
  try {
    var r = await fetch(url, { signal: AbortSignal.timeout(8000) });
    var j = await r.json();
    var klines = (j.data && j.data.klines) ? j.data.klines : [];
    return klines.map(function(k) {
      var parts = k.split(',');
      return { date:parts[0], open:+parts[1], close:+parts[2], high:+parts[3], low:+parts[4], vol:+parts[5] };
    });
  } catch(e) { return []; }
}

// ── 技术指标 ──────────────────────────────────────
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
  var out = new Array(prices.length).fill(null);
  var seed = 0;
  for (var i = 0; i < n; i++) seed += prices[i];
  out[n-1] = seed / n;
  for (var i = n; i < prices.length; i++)
    out[i] = prices[i] * k + out[i-1] * (1-k);
  return out;
}

function MACD(prices, f, s, sig) {
  f = f||12; s = s||26; sig = sig||9;
  var ef = EMA(prices, f), es = EMA(prices, s);
  var dif = new Array(prices.length).fill(null);
  for (var i = s-1; i < prices.length; i++) dif[i] = ef[i] - es[i];
  var sk = 2/(sig+1);
  var se = new Array(prices.length).fill(null);
  se[s-1] = dif[s-1];
  for (var i = s; i < dif.length; i++) se[i] = dif[i]*sk + se[i-1]*(1-sk);
  var hist = dif.map(function(v,i){ return v===null?null:v-se[i]; });
  return { dif: dif, sig: se, hist: hist };
}

function pctReturn(C, data, n) {
  if (n > 0 && C.length > n) {
    // ── v3.7修复：数据新鲜度校验 ──────────────────────────
    // 若最新K线距今超过5个交易日，说明数据有断档，
    // 用日期查找而非索引查找，避免因节假日缺口导致20日涨幅失真
    if (data && data.length > 0) {
      var todayStr   = data[data.length - 1].date;
      var todayParts = todayStr.split('-').map(Number);
      var todayMs    = new Date(todayParts[0], todayParts[1]-1, todayParts[2]).getTime();
      var nowMs      = Date.now();
      var gapDays    = Math.round((nowMs - todayMs) / 86400000);
      if (gapDays > 5) {
        // 数据陈旧，改用日期查找
        var targetDate = new Date(todayMs - n * 86400000); // 估算目标日期
        var targetStr = targetDate.toISOString().slice(0,10);
        var idx = data.findIndex(function(d){ return d.date <= targetStr; });
        if (idx > 0) {
          var startPrice = C[idx - 1];
          var endPrice   = C[C.length - 1];
          if (startPrice > 0) return (endPrice - startPrice) / startPrice * 100;
        }
      }
    }
    // 正常情况：用索引差计算（交易日对齐）
    var startPrice = C[C.length - 1 - n];
    var endPrice   = C[C.length - 1];
    if (startPrice > 0) return (endPrice - startPrice) / startPrice * 100;
  }
  return null;
}

// ── Pearson相关系数（基于日收益率，v3.4修复）────────────────────
// v3.4修复：用日收益率替代收盘价，避免两者长期同向上涨导致的虚高
// 返回 R[i] 与 R2[j] 在重叠区间上的 Pearson r，[-1, 1]
function pearsonCorr(C1, C2) {
  // 1. 把收盘价序列转成日收益率序列
  function toReturns(prices) {
    var r = [];
    for (var i = 1; i < prices.length; i++) {
      if (prices[i] > 0 && prices[i-1] > 0)
        r.push((prices[i] - prices[i-1]) / prices[i-1]);
    }
    return r;
  }
  var R1 = toReturns(C1);
  var R2 = toReturns(C2);
  // 取最近60天（或两者的较短长度）
  var n = Math.min(R1.length, R2.length, 60);
  var s1 = R1.length - n, s2 = R2.length - n;
  var sumX=0, sumY=0, sumXY=0, sumX2=0, sumY2=0;
  for (var i = 0; i < n; i++) {
    var x = R1[s1+i], y = R2[s2+i];
    sumX+=x; sumY+=y; sumXY+=x*y; sumX2+=x*x; sumY2+=y*y;
  }
  var num = n*sumXY - sumX*sumY;
  var den = Math.sqrt((n*sumX2-sumX*sumX)*(n*sumY2-sumY*sumY));
  if (den === 0) return 0;
  return num / den;
}

// ── 相关性过滤（贪心算法）────────────────────────
// 从 BUY 候选中选出不与已选组合 maxCorr > 0.70 的标的
// 优先级：先星级高的，同星级 score 高的优先
function filterByCorrelation(buys) {
  if (buys.length <= 1) return buys;

  // 按星级(降) + score(降) 排序
  var sorted = buys.slice().sort(function(a,b){
    if (b.stars !== a.stars) return b.stars - a.stars;
    return b.score - a.score;
  });

  var selected = [];   // {code, name, stars, score, corr}

  for (var i = 0; i < sorted.length; i++) {
    var candidate = sorted[i];
    var maxCorr = 0;

    for (var j = 0; j < selected.length; j++) {
      var s = selected[j];
      if (s.corrData && candidate.corrData) {
        var r = pearsonCorr(s.corrData, candidate.corrData);
        if (r > maxCorr) maxCorr = r;
      }
    }

    // 如果相关性 ≤ 0.70，纳入；> 0.70 则标记为"相关过高"跳过
    if (maxCorr <= 0.70) {
      candidate.maxCorr = maxCorr;
      // 保留原始对象全部字段，避免后续输出/MD写入缺失数据
      selected.push(Object.assign({}, candidate));
    } else {
      // 记录被过滤的原因（相关性过高）
      candidate.filtered = true;
      candidate.maxCorr  = maxCorr;
      candidate.filterReason = '相关过高';
    }
  }

  // 合并结果：选中的 + 被过滤的（都返回，供报告展示）
  var filteredOut = sorted.filter(function(r){ return r.filtered; });
  return selected.concat(filteredOut);
}

// ── 五星评分 v3.1（统一版）────────────────────────
// 评分维度：趋势(5分) + 动量(4分) + 相对强弱(3分) + 成交量(1分) = 最高13分
// 星级（v3.7）：5星≥10分，4星≥8分，3星≥6分，2星≥4分，1星<4分
// v3.7修复：零轴上金叉改为+3分（原+1+2重复），五星门槛从11调至10分
function calcStarScore(data, benchmarkPct20) {
  if (data.length < 60) return { stars:1, score:0, details:{} };

  var C = data.map(function(d){ return d.close; });
  var V = data.map(function(d){ return d.vol; });

  var ma20  = SMA(C, 20);
  var ma50  = SMA(C, 50);
  var ma200 = SMA(C, 200);
  var macd  = MACD(C, 12, 26, 9);

  var i  = data.length - 1;
  var i1 = data.length - 2;
  var i3 = data.length - 4;  // 最近3天（前一天）

  var price  = C[i];
  var vol    = V[i];
  var volAvg = 0;
  for (var vi = i-19; vi <= i; vi++) volAvg += V[vi];
  volAvg = volAvg / 20;

  var ma20c = ma20[i],  ma20p1 = ma20[i1];
  var ma50c = ma50[i],  ma50p1 = ma50[i1];
  var ma200c= ma200[i];

  var d  = macd.dif[i],  dP1  = macd.dif[i1];
  var s  = macd.sig[i],  sP1  = macd.sig[i1];
  var h  = macd.hist[i], hP1  = macd.hist[i1];
  // MACD连续绿柱判断（最近3天）
  var h3 = macd.hist[i3];

  var pct5  = pctReturn(C, data, 5);
  var pct20 = pctReturn(C, data, 20);

  // ── 基础条件 ──
  var aboveMa20     = price > ma20c;
  var ma20Up        = ma20c >= ma20p1;       // MA20向上
  var ma50Up        = ma50c >= ma50p1;
  var ma20Above50   = ma50c ? ma20c > ma50c : false;
  var ma50Above200  = ma200c ? ma50c > ma200c : false;
  var maAbove50     = price > ma50c;
  var maAbove200    = ma200c ? price > ma200c : false;
  var macdAboveZero = d > 0 && s > 0;
  var goldX         = dP1 <= sP1 && d > s;   // 金叉（当天DIF上穿DEA）
  var deathX         = dP1 >= sP1 && d < s;   // 死叉
  var histUp         = h > 0 && h > hP1;      // 红柱放大
  var histGreen      = h < 0;                  // 当天MACD绿柱
  var histGreen3     = h < 0 && hP1 < 0 && h3 < 0;  // 连续3天绿柱
  var volSurge       = vol > volAvg * 1.5;     // 放量1.5倍（按v3.1策略）

  // ── 相对强弱（对比创业板指基准）──────────────
  var bmPct20 = benchmarkPct20 !== null ? benchmarkPct20 : 0;
  var relStr5  = pct5  !== null ? pct5  - bmPct20 * 0.25 : 0;
  var relStr20 = pct20 !== null ? pct20 - bmPct20 : 0;

  // ── 评分（13分制）───────────────────────────
  var score = 0;

  // 趋势得分 (0-5)
  if (aboveMa20)     score += 1;                          // 站上MA20
  if (ma20Above50)   score += 1;                          // MA20>MA50
  if (ma20Above50 && ma50Above200) score += 2;           // 多头排列（MA20>MA50>MA200）
  if (ma20Up)        score += 1;                          // MA20方向向上

  // 动量得分 (0-4)
  // ⚠️ v3.7修复："零轴上金叉"已隐含macdAboveZero=true，删除重复+1分
  if (goldX && macdAboveZero) score += 3;                 // 零轴上金叉（最佳买入信号，+3分）
  else if (goldX)             score += 1;                 // 零轴下金叉（弱，+1分）
  if (h > 0)                  score += 1;                 // 红柱（零轴上运行，非红柱放大）

  // 相对强弱 (0-3)
  if (relStr20 > 0)  score += 2;                          // 跑赢大盘20日
  if (relStr5  > 0)  score += 1;                          // 跑赢大盘5日

  // 成交量 (0-1)
  if (volSurge)      score += 1;                          // 放量1.5倍

  // ── 星级映射（v3.7修复：匹配新评分上限）────────────────────────────
  var stars = 1;
  if (score >= 10) stars = 5;    // 满分13分，零轴上金叉(+3)+多头排列(+2)+跑赢20日(+2)+站上MA20(+1)+MA20向上(+1)+红柱持续(+1)=10分
  else if (score >= 8) stars = 4;
  else if (score >= 6) stars = 3;
  else if (score >= 4) stars = 2;

  // ── 信号判断（v3.7修复：与新评分体系对齐）────────────────────
  // ⚠️ v3.2回测结论：MACD死叉、连续绿柱卖出规则全部劣于"仅用MA20跌破"
  // 持仓专用卖出触发 = 仅MA20跌破（或硬性止损5%）
  // 以下逻辑仅用于扫描时的信号分类（BUY/HOLD/WAIT），不作为卖出执行依据
  var signal = 'n';
  var tag    = '';

  if (!aboveMa20) {
    signal = 'n'; tag = '跌破MA20(等待)';
  } else if (goldX && macdAboveZero) {
    signal = 'B'; tag = '零轴上金叉(买入)';
  } else if (goldX) {
    signal = 'B'; tag = 'MACD金叉(买入)';
  } else if (macdAboveZero && h > 0) {
    signal = 'B'; tag = '零轴上方健康(买入)';
  } else if (macdAboveZero) {
    signal = 'H'; tag = '零轴上方持股';
  } else if (h > 0) {
    signal = 'H'; tag = '趋势向好持股';
  } else {
    signal = 'H'; tag = 'MACD弱势持股';  // 绿柱但价格仍在MA20上方，继续持有
  }

  return {
    stars:   stars,
    starStr: '⭐'.repeat(stars),
    score:   score,
    // 用于相关性计算的收益率序列（最近60天）
    corrData: C.slice(-60),
    // 诊断信息
    details: {
      aboveMa20:     aboveMa20,
      ma20Up:        ma20Up,
      ma20Above50:   ma20Above50,
      ma50Above200:  ma50Above200,
      macdAboveZero: macdAboveZero,
      goldX:         goldX,
      deathX:        deathX,
      histGreen3:    histGreen3,
      histUp:        histUp,
      relStr20:      relStr20,
      relStr5:       relStr5,
      volSurge:      volSurge,
      pct5:          pct5,
      pct20:         pct20,
    },
    // 卖出条件诊断（供持仓检查用）
    sellConditions: {
      priceBelowMA20:  !aboveMa20,
      macdDeathX:      deathX,
      macdGreen3Days:  histGreen3,
      price:            price,
      ma20:             ma20c,
      pct20:            pct20,
    },
    signal: signal,
    tag:    tag
  };
}

// ── 分析单只ETF ──────────────────────────────────
function analyze(data, etf, benchmarkPct20) {
  if (data.length < 30) return null;

  var starInfo = calcStarScore(data, benchmarkPct20);
  var C = data.map(function(d){ return d.close; });
  var i = data.length - 1;

  return {
    name:        etf.name,
    code:        etf.code,
    category:    etf.category,
    index:       etf.index,
    date:        data[i].date,
    price:       C[i],
    ma:          starInfo.details.aboveMa20
                  ? (SMA(C,20)[i] || 0).toFixed(3) : (SMA(C,20)[i] || 0).toFixed(3),
    maDir:       starInfo.details.ma20Up ? 'up' : 'dn',
    zone:        starInfo.details.macdAboveZero ? '上' : '下',
    pct5:        starInfo.details.pct5,
    pct20:       starInfo.details.pct20,
    signal:      starInfo.signal,
    tag:         starInfo.tag,
    score:       starInfo.score,
    stars:       starInfo.stars,
    starStr:     starInfo.starStr,
    corrData:    starInfo.corrData,
    // 相关性过滤用字段
    filtered:    false,
    maxCorr:     0,
    filterReason:'',
    // 详细诊断
    sellConditions: starInfo.sellConditions,
  };
}

// ── 基准指数分析 ──────────────────────────────────
function analyzeIndex(data, b) {
  if (data.length < 10) return null;
  var C = data.map(function(d){ return d.close; });
  var ma20 = SMA(C, 20);
  var macd  = MACD(C, 12, 26, 9);
  var i = data.length-1, i1 = data.length-2;

  var price=C[i], ma=ma20[i], maP1=ma20[i1];
  var d=macd.dif[i], s=macd.sig[i], h=macd.hist[i];
  var aboveZero = d>0 && s>0;

  var pct5  = pctReturn(C, data, 5);
  var pct20 = pctReturn(C, data, 20);

  return {
    name: b.name, type: b.type, code: b.code,
    date: data[i].date,
    price: price,
    ma: ma ? ma.toFixed(2) : null,
    maDir: maP1>=ma ? 'up' : 'dn',
    zone: aboveZero ? '上' : '下',
    pct5: pct5, pct20: pct20,
    trend: maP1>=ma ? (aboveZero?'强势':'偏强') : (aboveZero?'偏弱':'弱势'),
  };
}

// ── 主程序 ────────────────────────────────────────
async function main() {
  console.log('\n========================================');
  console.log('  全市场ETF信号扫描 v3.1  |  ' + ALL_ETFS.length + '只  |  MA20+MACD');
  console.log('========================================\n');

  // ── 1. 获取基准指数 ────────────────────────
  console.log('>> 正在获取主流指数基准...');
  var benchResults = [];
  var chiBianPct20 = null;

  for (var bi = 0; bi < BENCHMARKS.length; bi++) {
    var b = BENCHMARKS[bi];
    process.stdout.write('  ' + b.name + '... ');
    var data = await fetchIndex(b.code);
    await sleep(200);
    if (data.length >= 10) {
      var r = analyzeIndex(data, b);
      if (r) {
        benchResults.push(r);
        console.log(r.date + ' 收=' + r.price + '  MA20' + (r.maDir==='up'?'↗':'↘') +
          '  5日' + (r.pct5?r.pct5.toFixed(2)+'%':'--') +
          '  20日' + (r.pct20?r.pct20.toFixed(2)+'%':'--'));
        // 优先取创业板指作为基准
        if (r.name === '创业板指') chiBianPct20 = r.pct20;
      }
    } else {
      console.log('数据不足');
    }
  }

  // 降级：取沪深300，再降级：取任意A股指数
  if (chiBianPct20 === null) {
    for (var bx of benchResults) {
      if (bx.name === '沪深300') { chiBianPct20 = bx.pct20; break; }
    }
  }
  if (chiBianPct20 === null && benchResults.length > 0) {
    for (var bx of benchResults) {
      if (bx.type === 'A股') { chiBianPct20 = bx.pct20; break; }
    }
  }
  setBenchmark(chiBianPct20, null);
  console.log('>> 基准：创业板指20日涨幅 ' + (chiBianPct20 ? chiBianPct20.toFixed(2)+'%' : '未获取') + '\n');

  // ── 2. 扫描ETF ─────────────────────────────
  var results = [];
  for (var i = 0; i < ALL_ETFS.length; i++) {
    var etf = ALL_ETFS[i];
    process.stdout.write('[' + (i+1) + '/' + ALL_ETFS.length + '] ' + etf.name + ' (' + etf.code + ')... ');
    var data = await fetchTx(etf.code, etf.market);
    if (data.length < 30) {
      await sleep(400);
      data = await fetchEM(etf.code, etf.market);
    }
    await sleep(250);
    process.stdout.write(data.length + '条 ');
    if (data.length < 30) { console.log('FAIL'); continue; }

    var r = analyze(data, etf, chiBianPct20);
    if (r) {
      results.push(r);
      var flag = r.signal==='B' ? 'BUY' : r.signal==='H' ? 'HOLD' : 'WAIT';
      console.log(flag + ' ' + r.starStr + '  ' + r.date + '  ' +
        (r.pct20!=null ? r.pct20.toFixed(1)+'%' : '--') + '  ' + (r.tag||''));
    }
  }

  // ── 3. 相关性过滤（v3.1 P0核心修复）────────
  console.log('\n>> 正在计算相关性矩阵...');
  var buys = results.filter(function(r){ return r.signal==='B'; });
  var holds = results.filter(function(r){ return r.signal==='H'; });
  var waits = results.filter(function(r){ return r.signal==='n'; });

  var filteredResults = filterByCorrelation(buys);

  // 合并：相关性过滤后的 BUY（selected在前，filtered在后）
  var selectedBuys = filteredResults.filter(function(r){ return !r.filtered; });
  var filteredBuys = filteredResults.filter(function(r){ return r.filtered; });

  console.log('   BUY候选=' + buys.length + '  →  过滤后=' + selectedBuys.length +
    '  排除（相关过高）=' + filteredBuys.length);

  // ── 4. 合并最终结果 ────────────────────────
  // 最终 BUY = selectedBuys；HOLD = holds；WAIT = waits；FILTERED = filteredBuys（特殊标注）
  var finalBuys  = selectedBuys;
  var finalWaits = waits.concat(filteredBuys); // filtered BUY 并入 WAIT 列表（带标注）

  // 全部按星级+score排序
  function starScoreSort(a, b) {
    if (b.stars !== a.stars) return b.stars - a.stars;
    return b.score - a.score;
  }
  finalBuys.sort(starScoreSort);
  holds.sort(starScoreSort);
  finalWaits.sort(starScoreSort);

  // ── 5. 输出结果 ────────────────────────────
  console.log('\n========================================');
  console.log('  信号扫描结果  |  共'+results.length+'只ETF  |  v3.1');
  console.log('========================================');
  console.log('  买入='+finalBuys.length+'  持股='+holds.length+'  观望='+finalWaits.length+'\n');

  function pad(s, n) {
    s = String(s===null||s===undefined?'--':s);
    while (s.length < n) s = s + ' ';
    return s;
  }

  // 基准对比表
  console.log('----------------------------------------');
  console.log('  【市场基准指数今日表现】');
  console.log('----------------------------------------');
  var typeOrder = ['A股', '港股', '美股'];
  var byType = {};
  for (var t = 0; t < benchResults.length; t++) {
    var bx = benchResults[t];
    if (!byType[bx.type]) byType[bx.type] = [];
    byType[bx.type].push(bx);
  }
  for (var ti = 0; ti < typeOrder.length; ti++) {
    var tp = typeOrder[ti];
    if (!byType[tp]) continue;
    for (var xi = 0; xi < byType[tp].length; xi++) {
      var bx = byType[tp][xi];
      console.log('  ' + pad(bx.name,12) + ' 收=' + bx.price.toFixed(2) +
        '  MA20' + (bx.maDir==='up'?'↗向上':'↘向下') +
        '  零轴'+bx.zone +
        '  5日' + (bx.pct5!=null?bx.pct5.toFixed(2)+'%':'--') +
        '  20日' + (bx.pct20!=null?bx.pct20.toFixed(2)+'%':'--') +
        '  ' + bx.trend);
    }
  }

  var etfHeader = pad('类别',10) + pad('名称',14) + pad('代码',8) +
    pad('星级',6) + pad('收盘',8) + pad('MA20',7) + pad('方向',4) +
    pad('零轴',4) + pad('5日%',7) + pad('20日%',8);

  if (finalBuys.length > 0) {
    console.log('\n>> BUY (' + finalBuys.length + ')  [已通过相关性过滤]');
    console.log('  ' + etfHeader);
    for (var bj = 0; bj < finalBuys.length; bj++) {
      var r = finalBuys[bj];
      var corrNote = r.maxCorr > 0 ? '  ↔最大相关=' + r.maxCorr.toFixed(2) : '';
      console.log('  ' + pad(r.category,10) + pad(r.name,14) + pad(r.code,8) +
        pad(r.starStr,6) + pad((typeof r.price === 'number' ? r.price.toFixed(3) : '?'),8) +
        pad(r.ma||'?',7) + pad(r.maDir,4) + pad(r.zone,4) +
        pad((r.pct5!=null&&typeof r.pct5==='number'?r.pct5.toFixed(1)+'%':'--'),7) +
        pad((r.pct20!=null&&typeof r.pct20==='number'?r.pct20.toFixed(1)+'%':'--'),8) +
        corrNote
      );
    }
  }

  if (filteredBuys.length > 0) {
    console.log('\n>> BUY-FILTERED (' + filteredBuys.length + ')  [因相关性>0.70被排除]');
    console.log('  (括号内为与已选标的的最大相关性)');
    console.log('  ' + etfHeader);
    for (var bj = 0; bj < filteredBuys.length; bj++) {
      var r = filteredBuys[bj];
      console.log('  ' + pad(r.category,10) + pad(r.name,14) + pad(r.code,8) +
        pad(r.starStr,6) + pad((typeof r.price === 'number' ? r.price.toFixed(3) : '?'),8) +
        pad(r.ma||'?',7) + pad(r.maDir,4) + pad(r.zone,4) +
        pad((r.pct5!=null&&typeof r.pct5==='number'?r.pct5.toFixed(1)+'%':'--'),7) +
        pad((r.pct20!=null&&typeof r.pct20==='number'?r.pct20.toFixed(1)+'%':'--'),8) +
        '  [corr=' + r.maxCorr.toFixed(2) + ']'
      );
    }
  }

  if (holds.length > 0) {
    console.log('\n>> HOLD (' + holds.length + ')');
    console.log('  ' + etfHeader);
    for (var hk = 0; hk < holds.length; hk++) {
      var r = holds[hk];
      console.log('  ' + pad(r.category,10) + pad(r.name,14) + pad(r.code,8) +
        pad(r.starStr,6) + pad((typeof r.price === 'number' ? r.price.toFixed(3) : '?'),8) +
        pad(r.ma||'?',7) + pad(r.maDir,4) + pad(r.zone,4) +
        pad((r.pct5!=null&&typeof r.pct5==='number'?r.pct5.toFixed(1)+'%':'--'),7) +
        pad((r.pct20!=null&&typeof r.pct20==='number'?r.pct20.toFixed(1)+'%':'--'),8)
      );
    }
  }

  if (finalWaits.length > 0) {
    console.log('\n>> WAIT (' + finalWaits.length + ')');
    var byCat = {};
    for (var wk = 0; wk < finalWaits.length; wk++) {
      var r = finalWaits[wk];
      if (!byCat[r.category]) byCat[r.category] = [];
      byCat[r.category].push(r);
    }
    for (var catK in byCat) {
      var items = byCat[catK].map(function(x){
        return x.name + '(' + x.code + ')' +
          (x.filtered ? ' [排除:corr=' + x.maxCorr.toFixed(2) + ']' : '');
      });
      console.log('  [' + catK + '] ' + items.join(', '));
    }
  }

  // ── 6. 更新 etf_pool.md ───────────────────
  var scanDate = results[0] ? results[0].date : '--';
  var mdLines = [
    '# 全市场 ETF 完整清单（指数不重复）',
    '',
    '> 共 '+ALL_ETFS.length+' 只ETF | 策略：MA20+MACD v3.1 | 最多持仓5只 | 扫描日期：'+scanDate,
    '> **相关性过滤已启用**：BUY候选中 maxCorr > 0.70 的标的将被排除',
    '',
    '## 买入候选（' + finalBuys.length + '只，已通过相关性过滤）',
    '',
    '| 类别 | ETF名称 | 代码 | 星级 | 收盘 | MA20 | 方向 | 零轴 | 5日涨跌 | 20日涨跌 | 信号依据 |',
    '|------|---------|------|:----:|------|------|:----:|------|---------|---------|---------|'
  ];
  for (var bi2=0; bi2<finalBuys.length; bi2++) {
    var b2 = finalBuys[bi2];
    mdLines.push('| '+b2.category+' | '+b2.name+' | '+b2.code+' | '+b2.starStr+' | '+b2.price.toFixed(3)+' | '+b2.ma+' | '+(b2.maDir==='up'?'↗':'↘')+' | 零轴'+b2.zone+' | '+(b2.pct5!=null?b2.pct5.toFixed(1)+'%':'--')+' | '+(b2.pct20!=null?b2.pct20.toFixed(1)+'%':'--')+' | '+b2.tag+' |');
  }
  if (filteredBuys.length > 0) {
    mdLines.push('', '## 排除标的（相关性过高，共'+filteredBuys.length+'只）', '', '| 类别 | ETF名称 | 代码 | 星级 | 20日涨跌 | 最大相关 |', '|------|---------|------|:----:|---------|---------|');
    for (var bfi=0; bfi<filteredBuys.length; bfi++) {
      var bf = filteredBuys[bfi];
      mdLines.push('| '+bf.category+' | '+bf.name+' | '+bf.code+' | '+bf.starStr+' | '+(bf.pct20!=null?bf.pct20.toFixed(1)+'%':'--')+' | '+bf.maxCorr.toFixed(2)+' |');
    }
  }
  mdLines.push('', '## 持股待涨（'+holds.length+'只）', '', '| 类别 | ETF名称 | 代码 | 星级 | 收盘 | MA20 | 方向 | 零轴 | 5日涨跌 | 20日涨跌 |', '|------|---------|------|:----:|------|------|:----:|------|---------|---------|');
  for (var hi2=0; hi2<holds.length; hi2++) {
    var h2 = holds[hi2];
    mdLines.push('| '+h2.category+' | '+h2.name+' | '+h2.code+' | '+h2.starStr+' | '+h2.price.toFixed(3)+' | '+h2.ma+' | '+(h2.maDir==='up'?'↗':'↘')+' | 零轴'+h2.zone+' | '+(h2.pct5!=null?h2.pct5.toFixed(1)+'%':'--')+' | '+(h2.pct20!=null?h2.pct20.toFixed(1)+'%':'--')+' |');
  }
  mdLines.push('', '## 持币观望（'+finalWaits.length+'只）');
  var wCat = {};
  for (var wi=0; wi<finalWaits.length; wi++) {
    var w = finalWaits[wi];
    if (!wCat[w.category]) wCat[w.category] = [];
    wCat[w.category].push(w);
  }
  for (var wc in wCat) {
    mdLines.push('**['+wc+']**：' + wCat[wc].map(function(x){ return x.name+'('+x.code+')'; }).join('、'));
  }

  fs.writeFileSync(path.join(SCRIPT_DIR, 'etf_pool.md'), mdLines.join('\n'), 'utf8');
  console.log('\n[OK] etf_pool.md updated with v3.1 correlation filtering');

  // ── 7. 保存基准数据 ────────────────────────
  fs.writeFileSync(path.join(SCRIPT_DIR, 'benchmarks.json'),
    JSON.stringify(benchResults.map(function(bx){
      return { name:bx.name, type:bx.type, price:bx.price, ma:bx.ma,
               pct5:bx.pct5, pct20:bx.pct20, maDir:bx.maDir, zone:bx.zone, trend:bx.trend };
    }), null, 2), 'utf8');
}

main().catch(console.error);
