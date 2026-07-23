// ============================================================
// 沪深300 20年回测  MA20+MACD共振策略 vs 买入持有
// 数据源: 东方财富 K线 API (不复权)
// 运行: node backtest_hs300.js
// ============================================================

// -------------------- 数据获取 --------------------

async function fetchHS300(start = '20050401', end = '20260416') {
  console.log(`📥 正在从东方财富获取沪深300 K线数据...`);
  console.log(`   时间范围: ${start} ~ ${end}`);

  // 东方财富日K API
  const url = `https://push2his.eastmoney.com/api/qt/stock/kline/get` +
    `?secid=1.000300` +
    `&fields1=f1,f2,f3,f4,f5,f6` +
    `&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61` +
    `&klt=101` +         // 101 = 日K
    `&fqt=0` +           // 0 = 不复权
    `&beg=${start}` +
    `&end=${end}`;

  const resp = await fetch(url, { timeout: 30000 });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const j = await resp.json();
  const klines = j.data?.klines || [];
  if (klines.length === 0) throw new Error('数据为空');

  // 字段: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
  const data = klines.map(k => {
    const [date, open, close, high, low, vol] = k.split(',');
    return {
      date: date,
      open:  parseFloat(open),
      close: parseFloat(close),
      high:  parseFloat(high),
      low:   parseFloat(low),
      vol:   parseFloat(vol),
    };
  });

  console.log(`✅ 获取到 ${data.length} 条数据`);
  console.log(`   ${data[0].date} 收盘=${data[0].close}  →  ${data[data.length-1].date} 收盘=${data[data.length-1].close}\n`);
  return data;
}

// -------------------- 技术指标 --------------------

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
  const emaFast = calcEMA(prices, fast);
  const emaSlow = calcEMA(prices, slow);

  const dif = new Array(prices.length).fill(null);
  for (let i = slow - 1; i < prices.length; i++) {
    dif[i] = emaFast[i] - emaSlow[i];
  }

  const sigEma = new Array(prices.length).fill(null);
  let first = null;
  for (let i = slow - 1; i < prices.length; i++) {
    if (first === null) { first = dif[i]; sigEma[i] = dif[i]; }
    else { sigEma[i] = dif[i] * (2/(signal+1)) + sigEma[i-1] * (1 - 2/(signal+1)); }
  }

  const hist = new Array(prices.length).fill(null);
  for (let i = slow - 1; i < prices.length; i++) {
    hist[i] = dif[i] - sigEma[i];
  }

  return { dif, sig: sigEma, hist };
}

// -------------------- 回测引擎 --------------------

function runStrategy(data, initialCapital = 1_000_000) {
  const closes = data.map(d => d.close);
  const vols   = data.map(d => d.vol);

  const ma20 = calcSMA(closes, 20);
  const macd  = calcMACD(closes, 12, 26, 9);
  const { dif, sig, hist } = macd;

  let capital    = initialCapital;
  let position   = 0;
  let avgCost    = 0;
  let peak       = initialCapital;
  let maxDD      = 0;
  const trades   = [];
  const equity   = [];

  let posType = null;

  for (let i = 35; i < data.length; i++) {
    const price   = closes[i];
    const ma      = ma20[i];
    const maPrev  = ma20[i - 1];
    const maPrev2 = ma20[i - 2];
    const d       = dif[i];
    const dPrev   = dif[i - 1];
    const s       = sig[i];
    const sPrev   = sig[i - 1];
    const h       = hist[i];
    const hPrev   = hist[i - 1];
    const hPrev2  = hist[i - 2];
    const vol     = vols[i];
    const volPrev = vols[i - 1];

    const totalValue = capital + position * price;

    // ── 买入信号 ──
    if (posType === null && ma !== null && d !== null && h !== null) {
      const aboveMa  = price > ma;
      const maOk     = maPrev >= maPrev2;                         // MA20走平或向上
      const goldX    = dPrev <= sPrev && d > s;                    // MACD金叉
      const strongX  = d > 0 && s > 0 && h > 0 && h > hPrev;     // 0轴上方红柱放大
      const macdOK   = goldX || strongX;
      const volOK    = vol >= volPrev * 0.5;                       // 量能未明显萎缩

      if (aboveMa && maOk && macdOK && volOK) {
        const shares = Math.floor(capital / price);
        if (shares > 0) {
          avgCost   = price;
          position  = shares;
          capital   = capital - shares * price;
          posType   = 'long';
          trades.push({
            type: 'BUY', date: data[i].date,
            price, shares,
            value: shares * price,
            reason: goldX ? 'MA20向上+MACD金叉' : 'MA20向上+0轴上方红柱放大'
          });
        }
      }
    }

    // ── 卖出信号 ──
    if (posType === 'long' && position > 0) {
      const belowMa    = price < ma;                           // ①破MA20
      const loss5pct   = (price - avgCost) / avgCost <= -0.05; // ④硬止损-5%
      const deadX      = dPrev > sPrev && d < s;               // ②MACD死叉
      const histGreen  = h < 0 && hPrev >= 0;                  // ②红柱转绿

      let reason = null;
      if (belowMa)   reason = '跌破MA20';
      else if (loss5pct) reason = '硬性止损-5%';
      else if (deadX)   reason = 'MACD死叉';
      else if (histGreen) reason = 'MACD红柱转绿';

      if (reason) {
        capital += position * price;
        trades.push({
          type: 'SELL', date: data[i].date,
          price, shares: position,
          value: position * price,
          pnl: ((price - avgCost) / avgCost * 100).toFixed(2) + '%',
          reason
        });
        position = 0; avgCost = 0; posType = null;
      }
    }

    equity.push({ date: data[i].date, value: capital + position * price });
    if (equity[equity.length - 1].value > peak) peak = equity[equity.length - 1].value;
    const dd = (peak - equity[equity.length - 1].value) / peak * 100;
    if (dd > maxDD) maxDD = dd;
  }

  // 强制平仓
  if (position > 0) {
    const lastP = closes[data.length - 1];
    capital += position * lastP;
    trades.push({
      type: 'SELL', date: data[data.length - 1].date,
      price: lastP, shares: position,
      value: position * lastP,
      pnl: ((lastP - avgCost) / avgCost * 100).toFixed(2) + '%',
      reason: '回测结束强制平仓'
    });
  }

  return { trades, equity, finalValue: capital, maxDD, peak };
}

// -------------------- 买入持有 --------------------

function runBuyHold(data, initialCapital = 1_000_000) {
  const firstPrice = data[0].close;
  const lastPrice  = data[data.length - 1].close;
  const shares     = Math.floor(initialCapital / firstPrice);
  const cost       = shares * firstPrice;
  const finalValue = shares * lastPrice;
  const years      = (new Date(data[data.length-1].date) - new Date(data[0].date)) / (365.25 * 864e5);
  return { cost, finalValue, shares, firstPrice, lastPrice, years };
}

// -------------------- 统计 --------------------

function stats(equity, initialCapital, maxDD) {
  const finalV   = equity[equity.length - 1].value;
  const totalRet = (finalV - initialCapital) / initialCapital;
  const years    = (new Date(equity[equity.length-1].date) - new Date(equity[0].date)) / (365.25 * 864e5);
  const cagr     = Math.pow(finalV / initialCapital, 1 / years) - 1;

  const rets = [];
  for (let i = 1; i < equity.length; i++)
    rets.push((equity[i].value - equity[i-1].value) / equity[i-1].value);
  const avgR  = rets.reduce((a,b)=>a+b,0) / rets.length;
  const stdR  = Math.sqrt(rets.reduce((a,b)=>a+(b-avgR)**2,0) / rets.length);
  const annStd = stdR * Math.sqrt(252);
  const sharpe  = annStd > 0 ? (cagr - 0.03) / annStd : 0;
  const winRate = rets.filter(r=>r>0).length / rets.length;

  return { finalV, totalRet, cagr, sharpe, winRate, maxDD };
}

// -------------------- 主程序 --------------------

async function main() {
  console.log('\n' + '='.repeat(60));
  console.log('   沪深300 20年回测  MA20+MACD共振  vs  买入持有');
  console.log('='.repeat(60) + '\n');

  let data;
  try {
    data = await fetchHS300('20050401', '20260416');
  } catch (err) {
    console.error('❌ 数据获取失败:', err.message);
    process.exit(1);
  }

  if (data.length < 1000) { console.error('❌ 数据不足'); process.exit(1); }

  const ICAP = 1_000_000;

  console.log('🔄 运行 MA20+MACD 策略回测...\n');
  const strat = runStrategy(data, ICAP);
  const ss    = stats(strat.equity, ICAP, strat.maxDD);

  console.log('🔄 运行买入持有基准...\n');
  const bh    = runBuyHold(data, ICAP);
  const bhCAGR = Math.pow(bh.finalValue / bh.cost, 1 / bh.years) - 1;

  // ── 对比表 ──
  console.log('='.repeat(60));
  console.log('   回测结果对比');
  console.log('='.repeat(60));
  console.log(`   回测区间:  ${data[0].date}  →  ${data[data.length-1].date}`);
  console.log(`   初始资金:  ¥${ICAP.toLocaleString()}`);
  console.log(`   沪深300:   ${data[0].close}  →  ${data[data.length-1].close}  涨幅 ${((data[data.length-1].close/data[0].close-1)*100).toFixed(1)}%\n`);

  const rows = [
    ['期末资金',        `¥${ss.finalV.toFixed(0)}`,                 `¥${bh.finalValue.toFixed(0)}`],
    ['总收益率',        `${(ss.totalRet*100).toFixed(2)}%`,          `${((bh.finalValue/bh.cost-1)*100).toFixed(2)}%`],
    ['年化收益率',      `${(ss.cagr*100).toFixed(2)}%`,             `${(bhCAGR*100).toFixed(2)}%`],
    ['最大回撤',        `${ss.maxDD.toFixed(2)}%`,                  '—'],
    ['夏普比率',        `${ss.sharpe.toFixed(2)}`,                  '—'],
    ['日胜率',         `${(ss.winRate*100).toFixed(1)}%`,           '—'],
  ];

  console.log('   ┌──────────────────┬──────────────────┬──────────────────┐');
  console.log('   │ 指标             │   MA20+MACD策略  │     买入持有     │');
  console.log('   ├──────────────────┼──────────────────┼──────────────────┤');
  for (const [k, v1, v2] of rows) {
    console.log(`   │ ${k.padEnd(15)} │ ${v1.padEnd(16)} │ ${v2.padEnd(16)} │`);
  }
  console.log('   └──────────────────┴──────────────────┴──────────────────┘');

  const diff = ss.finalV - bh.finalValue;
  console.log(`\n   💡 策略累计 ${diff >= 0 ? '跑赢' : '跑输'} 买入持有  ¥${Math.abs(diff).toFixed(0)}`);

  // ── 交易统计 ──
  console.log('\n' + '-'.repeat(60));
  console.log('   交易统计');
  console.log('-'.repeat(60));
  const buys  = strat.trades.filter(t => t.type === 'BUY');
  const sells = strat.trades.filter(t => t.type === 'SELL').filter(t => !t.reason?.includes('强制'));
  console.log(`   总交易次数:  ${buys.length} 次买入  /  ${sells.length} 次卖出`);
  if (sells.length > 0) {
    const pnls = sells.map(t => parseFloat(t.pnl));
    const wins  = pnls.filter(p => p > 0);
    const loses = pnls.filter(p => p <= 0);
    console.log(`   盈利次数:    ${wins.length}  (${(wins.length/sells.length*100).toFixed(1)}%)`);
    console.log(`   亏损次数:    ${loses.length}  (${(loses.length/sells.length*100).toFixed(1)}%)`);
    console.log(`   平均盈利:    +${(wins.reduce((a,b)=>a+b,0)/wins.length||0).toFixed(2)}%`);
    console.log(`   平均亏损:    ${(loses.reduce((a,b)=>a+b,0)/loses.length||0).toFixed(2)}%`);
    console.log(`   盈亏比:      ${(Math.abs(wins.reduce((a,b)=>a+b,0)/wins.length) / Math.abs(loses.reduce((a,b)=>a+b,0)/loses.length)).toFixed(2)}`);
  }

  // ── 完整交易记录 ──
  console.log('\n' + '-'.repeat(60));
  console.log('   完整交易记录');
  console.log('-'.repeat(60));
  for (const t of strat.trades) {
    if (t.type === 'BUY') {
      console.log(`   🟢 ${t.date} 买入  ${t.shares.toLocaleString()}股 @ ¥${t.price.toFixed(2)}  总额¥${t.value.toFixed(0)}  [${t.reason}]`);
    } else {
      console.log(`   🔴 ${t.date} 卖出 ${t.shares.toLocaleString()}股 @ ¥${t.price.toFixed(2)}  总额¥${t.value.toFixed(0)}  ${t.pnl}  [${t.reason}]`);
    }
  }

  // ── 保存净值曲线 CSV ──
  const fs = await import('fs');
  const csvLines = ['date,strategy_value,buyhold_value'];
  for (let i = 0; i < strat.equity.length; i++) {
    const { date, value } = strat.equity[i];
    // 买入持有净值对齐策略起点
    const startDate = strat.equity[0].date;
    const bhIdx = data.findIndex(d => d.date === date);
    if (bhIdx >= 0) {
      const bhValue = bh.shares * data[bhIdx].close + (bh.cost - bh.shares * bh.firstPrice);
      csvLines.push(`${date},${value.toFixed(2)},${bhValue.toFixed(2)}`);
    }
  }
  fs.writeFileSync('backtest_equity.csv', csvLines.join('\n'), 'utf8');
  console.log('\n📁 净值曲线已保存: backtest_equity.csv');

  console.log('\n' + '='.repeat(60));
  console.log('   ⚠️  风险提示：回测结果不代表未来收益，实盘请谨慎！');
  console.log('='.repeat(60));
}

main().catch(console.error);
