// 扫描5只ETF的MA20+MACD信号
// 沪交所=1.XXXXXX  深交所=0.XXXXXX
const ETFS = [
  {secid: '1.510300', name: '沪深300ETF', alias: '510300'},
  {secid: '0.159922', name: '中证500ETF', alias: '159922'},
  {secid: '0.159915', name: '创业板ETF',  alias: '159915'},
  {secid: '1.588000', name: '科创50ETF',  alias: '588000'},
  {secid: '0.159628', name: '中证1000ETF',alias: '159628'},
];

async function getKline(secid) {
  const url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get' +
    '?secid=' + secid +
    '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61' +
    '&klt=101&fqt=0&beg=20250101&end=20260416&lmt=120';
  const r = await fetch(url);
  return r.json();
}

function calcSMA(prices, period) {
  const out = new Array(prices.length).fill(null);
  for (let i = period - 1; i < prices.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += prices[j];
    out[i] = sum / period;
  }
  return out;
}

function calcEMA(prices, period) {
  const k = 2 / (period + 1);
  const out = new Array(prices.length).fill(null);
  out[period - 1] = prices.slice(0, period).reduce((a, b) => a + b) / period;
  for (let i = period; i < prices.length; i++) {
    out[i] = prices[i] * k + out[i - 1] * (1 - k);
  }
  return out;
}

function calcMACD(prices, fast = 12, slow = 26, signal = 9) {
  const ef = calcEMA(prices, fast);
  const es = calcEMA(prices, slow);
  const dif = new Array(prices.length).fill(null);
  for (let i = slow - 1; i < prices.length; i++) dif[i] = ef[i] - es[i];
  const sig = new Array(prices.length).fill(null);
  sig[slow - 1] = dif[slow - 1];
  for (let i = slow; i < prices.length; i++)
    sig[i] = dif[i] * (2/(signal+1)) + sig[i-1] * (1 - 2/(signal+1));
  const hist = dif.map((v, i) => v === null ? null : v - sig[i]);
  return { dif, sig, hist };
}

function analyze(data, name) {
  if (data.length < 30) return null;
  const closes = data.map(d => d.close);
  const vols   = data.map(d => d.vol);
  const ma20   = calcSMA(closes, 20);
  const { dif, sig, hist } = calcMACD(closes, 12, 26, 9);

  const i = data.length - 1;       // 今天
  const i1 = data.length - 2;     // 昨天
  const i2 = data.length - 3;       // 前天

  const price   = closes[i];
  const pPrev   = closes[i1];
  const ma      = ma20[i];
  const maPrev  = ma20[i1];
  const maPrev2 = ma20[i2];
  const d       = dif[i];
  const dPrev   = dif[i1];
  const s       = sig[i];
  const sPrev   = sig[i1];
  const h       = hist[i];
  const hPrev   = hist[i1];
  const hPrev2  = hist[i2];
  const vol     = vols[i];
  const volPrev = vols[i1];
  const date    = data[i].date;

  const aboveMa   = price > ma;
  const maOk      = maPrev >= maPrev2;
  const goldX     = dPrev <= sPrev && d > s;
  const aboveZero = d > 0 && s > 0;
  const histGrow  = h > 0 && h > hPrev;
  const volOk     = vol >= volPrev * 0.5;

  const deadX     = dPrev >= sPrev && d < s;
  const histGreen = h < 0 && hPrev >= 0;

  // 判断信号
  let signal = null;
  let strength = '';
  if (!aboveMa) {
    signal = '持币';
  } else if (!maOk) {
    signal = '持币(MA20未向上)';
  } else if (goldX) {
    signal = aboveZero ? '⭐⭐⭐强烈买入' : '⭐⭐买入';
    strength = aboveZero ? '0轴上方金叉' : '0轴下方金叉';
  } else if (aboveZero && histGrow && h > 0) {
    signal = '⭐⭐强势买入';
    strength = '0轴上红柱放大';
  } else if (aboveZero && h > 0) {
    signal = '⭐持股待涨';
    strength = '0轴上持股';
  } else {
    signal = '⭐持股观望';
    strength = '趋势向好';
  }

  return {
    name, date, price,
    ma: ma?.toFixed(3),
    maDir: maPrev >= maPrev2 ? '↗向上' : maPrev < maPrev2 ? '↘向下' : '→走平',
    dif: d?.toFixed(3), sig: s?.toFixed(3), hist: h?.toFixed(3),
    dif0: d > 0 ? '零轴上' : '零轴下',
    signal, strength,
    aboveMa, maOk, goldX, aboveZero, histGrow, volOk,
    deadX, histGreen,
  };
}

async function main() {
  const results = [];
  for (const etf of ETFS) {
    const j = await getKline(etf.secid);
    const klines = j.data?.klines || [];
    const data = klines.map(k => {
      const [date, open, close, high, low, vol] = k.split(',');
      return { date, open: +open, close: +close, high: +high, low: +low, vol: +vol };
    });
    const r = analyze(data, etf.name);
    if (r) results.push(r);
  }

  // 打印结果
  console.log('\n📊 ETF 信号扫描报告  (2026-04-16 收盘)');
  console.log('='.repeat(80));
  console.log('ETF          日期         收盘     MA20    MA方向  DIF    DEA   柱子   零轴  信号              强度');
  console.log('-'.repeat(80));
  for (const r of results) {
    console.log(
      `${r.name.padEnd(10)} ${r.date} ${r.price.toFixed(3).padEnd(9)} ${(r.ma||'?').padEnd(8)} ${r.maDir.padEnd(5)} ` +
      `${(r.dif||'?').padEnd(7)} ${(r.sig||'?').padEnd(7)} ${(r.hist||'?').padEnd(7)} ${r.dif0.padEnd(5)} ` +
      `${r.signal.padEnd(14)} ${r.strength}`
    );
  }

  // 买入推荐
  const buys = results.filter(r => r.signal?.startsWith('⭐'));
  console.log('\n🟢 买入候选ETF:');
  if (buys.length === 0) {
    console.log('  今日无符合买入条件的ETF，持币观望');
  } else {
    for (const b of buys) {
      console.log(`  【${b.name}】${b.signal}  收盘=${b.price}  MA20=${b.ma}  ${b.strength}`);
    }
  }

  // 持仓检查（无持仓，本次不输出）
  console.log('\n📋 当前持仓状态: 空仓');
}

main().catch(console.error);
