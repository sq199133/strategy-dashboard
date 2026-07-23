const fs = require('fs');
const buf = fs.readFileSync('D:/QClaw_Trading/scripts/backtest/_port_out.txt');
const text = buf.toString('latin1');

// Decode GBK fragments using known ETF names
const known = {
  'sh515880': '黄金ETF(博时)', 'sh588000': '纳指ETF(易方达)', 'sh588200': '科创50ETF(易方达)',
  'sh588030': '纳指100ETF(易方达)', 'sh588100': '纳指ETF(华夏)', 'sh588730': '纳指ETF(华夏)',
  'sh588170': '科创50ETF(华夏)', 'sh512400': '煤炭ETF(国泰)', 'sh516160': '新能源ETF(华夏)',
  'sh516510': 'AI算力ETF', 'sh589000': '科创综指ETF', 'sh518880': '黄金ETF(华安)',
  'sh512660': '军工ETF(国泰)', 'sh517520': '创业板ETF(华夏)', 'sh510880': '红利ETF(华泰)',
  'sh512890': '红利ETF低波', 'sh512480': '科创50ETF(华夏)', 'sh512910': 'A100ETF',
  'sh560050': 'A50ETF(摩根)', 'sh515080': 'A50ETF(招商)', 'sh515220': '能源ETF(华夏)',
  'sz159320': '纳指ETF(华夏)', 'sz159782': '中证A50ETF(摩根)', 'sz159915': '创业板ETF(易方达)',
  'sz159949': '创业板50ETF', 'sz159819': '创新药ETF(华夏)', 'sz159870': '生物医药ETF',
  'sz159610': '中证500ETF(方正)', 'sz159677': '中证1000ETF(摩根)', 'sz159625': '中证A50ETF(万家)',
  'sz159647': '中证A50ETF(华夏)', 'sz159332': '中证A50ETF(永赢)', 'sz159551': '医疗器械ETF(国瑞)'
};

const lines = text.split('\n');
console.log('=== 组合回测结果解码 ===\n');
for (const l of lines) {
  const s = l.trim();
  if (!s) continue;
  if (pct(s) >= 10) continue;
  // Replace codes with names
  let out = s;
  for (const [code, name] of Object.entries(known)) {
    out = out.replace(new RegExp(code, 'g'), name);
  }
  // Fix GBK garbled chars
  out = out.replace(/[ÿþ]/g, '');
  if (out.match(/\d+\.\d{2,3}/) || out.match(/Loaded|Candidate|Selected|Common|Portfolio|sharpe|Sharpe|ß|ÞVKm|g'Y|TÞVKm|Ó~|6eÊv|t^S6e|1\.0t^/) || out.match(/[A-Za-z]{2}[0-9]{5,6}/)) {
    console.log(out);
  }
}

function pct(s) { return (s.match(/%/g)||[]).length; }
