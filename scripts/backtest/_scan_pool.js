// ETF池质量扫描 - 使用修正后的数据格式
const fs = require('fs');
const path = require('path');

function getRecords(raw) {
  if (!raw) return null;
  if (Array.isArray(raw)) return raw;
  if (raw.records) {
    if (Array.isArray(raw.records)) return raw.records;
    if (raw.records.days) return raw.records.days;
    if (raw.records.qfqday) return raw.records.qfqday;
    if (raw.records.day) return raw.records.day;
  }
  return null;
}

function getClose(d) {
  if (!d) return 0;
  if (typeof d === 'number') return d;
  return d.close || d.c || d.C || d.price || 0;
}

function calcStats(closes) {
  if (!closes || closes.length < 30) return null;
  const valid = closes.filter(v => v > 0);
  if (valid.length < 30) return null;
  const ret = valid.slice(1).map((p, i) => Math.log(p / valid[i]));
  const mean = ret.reduce((a, b) => a + b, 0) / ret.length;
  const variance = ret.reduce((a, b) => a + (b - mean) ** 2, 0) / ret.length;
  const std = Math.sqrt(variance);
  const vol = std * Math.sqrt(252);
  const ann = mean * 252;
  const sharpe = vol > 0.001 ? ann / vol : 0;
  return { sharpe, ann, vol, n: valid.length, maxClose: Math.max(...valid), minClose: Math.min(...valid) };
}

const histDir = 'D:\\QClaw_Trading\\data\\history';
const files = fs.readdirSync(histDir).filter(f => f.endsWith('.json'));
let results = [];

for (const f of files) {
  const code = f.replace('.json', '');
  const raw = JSON.parse(fs.readFileSync(path.join(histDir, f), 'utf8'));
  const recs = getRecords(raw);
  const closes = recs ? recs.map(getClose) : [];
  const stats = calcStats(closes);
  if (!stats) continue;
  results.push({
    code,
    name: raw.name || code,
    ...stats,
    priceRange: (stats.maxClose / stats.minClose).toFixed(1) + 'x'
  });
}

// Sort by Sharpe descending
results.sort((a, b) => b.sharpe - a.sharpe);

console.log('═══════════════════════════════════════════════════════════════');
console.log('  ETF池质量总览 (按夏普比率降序)');
console.log('═══════════════════════════════════════════════════════════════');
console.log('代码       | 名称                  | 夏普  | 年化   | 波动率 | 数据条数');
console.log('────────── | ───────────────────── | ───── | ────── | ────── | ───────');
results.forEach(r => {
  const flag = r.sharpe >= 1.0 ? '★' : r.sharpe >= 0.5 ? '☆' : ' ';
  console.log(`${flag}${r.code} | ${(r.name).padEnd(18)} | ${r.sharpe.toFixed(3)} | ${(r.ann*100).toFixed(1)}% | ${(r.vol*100).toFixed(1)}% | ${r.n}`);
});

console.log(`\n总计: ${results.length} 只ETF`);
console.log(`夏普>=1.0: ${results.filter(r=>r.sharpe>=1.0).length} 只`);
console.log(`夏普>=0.5: ${results.filter(r=>r.sharpe>=0.5).length} 只`);
console.log(`夏普<0: ${results.filter(r=>r.sharpe<0).length} 只`);

// Save quality pool: top ETFs with sufficient data and good Sharpe
const qualityPool = results.filter(r => r.n >= 200 && r.sharpe >= 0.8)
  .slice(0, 20)
  .map(r => ({ code: r.code, name: r.name, sharpe: +r.sharpe.toFixed(3), ann: +(r.ann*100).toFixed(2), vol: +(r.vol*100).toFixed(2), n: r.n }));

fs.writeFileSync(
  path.join('D:\\QClaw_Trading\\data', 'etf_pool_quality.json'),
  JSON.stringify({ generated: new Date().toISOString(), pools: { 'quality_top20': qualityPool } }, null, 2)
);
console.log('\n已保存 quality_top20 到 etf_pool_quality.json');
