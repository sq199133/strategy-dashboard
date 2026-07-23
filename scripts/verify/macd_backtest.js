/**
 * MACD卖出条件回测对比
 * 目的：验证"死叉"和"红柱转绿"是否重复
 */

const MACD_PERIOD = { fast: 12, slow: 26, signal: 9 };

// 计算EMA
function ema(data, period) {
  const k = 2 / (period + 1);
  const result = [data[0]];
  for (let i = 1; i < data.length; i++) {
    result.push(data[i] * k + result[i - 1] * (1 - k));
  }
  return result;
}

// 计算MACD
function calcMACD(close) {
  const ema12 = ema(close, 12);
  const ema26 = ema(close, 26);
  const dif = ema12.map((v, i) => v - ema26[i]);
  const dea = ema(dif, 9);
  const macd = dif.map((v, i) => (v - dea[i]) * 2);
  return { dif, dea, macd };
}

// 检测信号
function detectSignals(dif, dea, macd) {
  const signals = [];
  
  for (let i = 1; i < macd.length; i++) {
    // 死叉：DIF从上往下穿过DEA
    const deathCross = dif[i-1] > dea[i-1] && dif[i] < dea[i];
    
    // 红转绿：MACD柱从正变负
    const redToGreen = macd[i-1] > 0 && macd[i] < 0;
    
    // 记录信号
    if (deathCross || redToGreen) {
      signals.push({
        day: i,
        deathCross,
        redToGreen,
        sameDay: deathCross && redToGreen, // 是否同一天触发
        dif: dif[i].toFixed(4),
        dea: dea[i].toFixed(4),
        macd: macd[i].toFixed(4)
      });
    }
  }
  
  return signals;
}

// 模拟数据（简化的上涨后下跌场景）
function generateTestData(days = 60) {
  const close = [];
  let price = 10;
  
  for (let i = 0; i < days; i++) {
    if (i < 20) {
      // 上涨阶段
      price += Math.random() * 0.3 + 0.05;
    } else if (i < 30) {
      // 横盘
      price += (Math.random() - 0.5) * 0.2;
    } else {
      // 下跌阶段
      price -= Math.random() * 0.25 + 0.05;
    }
    close.push(price);
  }
  
  return close;
}

// 运行多次模拟
console.log('=== MACD卖出条件回测分析 ===\n');
console.log('模拟场景：上涨 → 横盘 → 下跌\n');

let totalSignals = 0;
let sameDayCount = 0;
let deathOnly = 0;
let redOnly = 0;

for (let run = 0; run < 100; run++) {
  const close = generateTestData(80);
  const { dif, dea, macd } = calcMACD(close);
  const signals = detectSignals(dif, dea, macd);
  
  signals.forEach(s => {
    totalSignals++;
    if (s.sameDay) sameDayCount++;
    else if (s.deathCross) deathOnly++;
    else if (s.redToGreen) redOnly++;
  });
}

console.log('统计结果（100次模拟）：');
console.log(`总信号数: ${totalSignals}`);
console.log(`同一天触发: ${sameDayCount} (${(sameDayCount/totalSignals*100).toFixed(1)}%)`);
console.log(`仅死叉: ${deathOnly} (${(deathOnly/totalSignals*100).toFixed(1)}%)`);
console.log(`仅红转绿: ${redOnly} (${(redOnly/totalSignals*100).toFixed(1)}%)`);

console.log('\n=== 结论 ===');
console.log('死叉和红柱转绿在绝大多数情况下（>95%）是同一天触发');
console.log('这两个条件本质上是重复的，建议保留其中一个即可。\n');

// 更详细的单次分析
console.log('=== 单次详细分析 ===\n');
const close = generateTestData(80);
const { dif, dea, macd } = calcMACD(close);
const signals = detectSignals(dif, dea, macd);

console.log('检测到的卖出信号：');
console.log('天数 | 死叉 | 红转绿 | 同一天 |   DIF   |   DEA   |  MACD柱');
console.log('-----|------|--------|--------|---------|---------|--------');
signals.slice(0, 10).forEach(s => {
  console.log(`${String(s.day).padStart(4)} | ${s.deathCross ? ' ✓ ' : '   '} | ${s.redToGreen ? '  ✓   ' : '      '} | ${s.sameDay ? '  ✓   ' : '      '} | ${s.dif} | ${s.dea} | ${s.macd}`);
});

console.log('\n=== 策略优化建议 ===\n');
console.log('方案A：保留"MACD柱由正转负"（简洁）');
console.log('  - 条件：MACD柱 < 0 且 前一日MACD柱 > 0');
console.log('  - 优点：直观，易计算');
console.log('');
console.log('方案B：保留"MACD死叉"（传统）');
console.log('  - 条件：DIF < DEA 且 前一日DIF > DEA');
console.log('  - 优点：技术分析经典信号');
console.log('');
console.log('方案C：改为"MACD柱连续变绿3天"（减少假信号）');
console.log('  - 条件：连续3天MACD柱 < 0');
console.log('  - 优点：过滤短期波动，更可靠');
console.log('');
console.log('推荐：方案A或C，与"价格跌破MA20"组合使用即可。');
