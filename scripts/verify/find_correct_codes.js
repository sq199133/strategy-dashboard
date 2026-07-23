// Search etf_all_raw.json for correct codes matching our intended funds
const fs = require('fs');
const path = require('path');

const all = JSON.parse(fs.readFileSync(path.join(__dirname, 'etf_all_raw.json'), 'utf8'));

function search(keyword, category) {
  const kw = keyword.toLowerCase();
  return all.filter(e => {
    const nameLower = e.name.toLowerCase();
    if (category === 'bio') return /医药|生物|中药|医疗|保健|健康|疫苗|基因/.test(e.name);
    if (category === 'military') return /军工|国防|航天|航空|武器|军用/.test(e.name);
    if (category === 'ev') return /新能源车|新能车|电动汽车|智能汽车/.test(e.name);
    if (category === 'nasdaq') return /纳斯达克|纳指|美国|美股/.test(e.name);
    if (category === '500') return /中证500/.test(e.name);
    if (category === '1000') return /中证1000/.test(e.name);
    return nameLower.includes(kw);
  }).sort((a,b) => b.size - a.size);
}

const keywords = [
  {kw:'生物医药', cat:'bio'},
  {kw:'军工', cat:'military'},
  {kw:'新能源车', cat:'ev'},
  {kw:'纳斯达克', cat:'nasdaq'},
  {kw:'标普500', cat:'sp500'},
  {kw:'日经225', cat:'nikkei'},
  {kw:'中证1000', cat:'1000'},
  {kw:'煤炭', cat:'coal'},
  {kw:'黄金', cat:'gold'},
  {kw:'白银', cat:'silver'},
  {kw:'红利', cat:'dividend'},
  {kw:'保险', cat:'insurance'},
];

keywords.forEach(({kw, cat}) => {
  const r = search(kw, cat);
  if (r.length > 0) {
    console.log('\n[' + kw + '] (规模>=1亿)');
    r.slice(0,8).forEach(e => console.log('  ' + e.code + ' ' + e.name + ' (' + e.market + ') ' + e.size.toFixed(1) + '亿'));
  }
});

// Also search all ETFs by code prefix
console.log('\n\n=== 5字上海ETF（跨境/QDII常见）===');
all.filter(e => e.market==='SH' && e.code.startsWith('513')).forEach(e => {
  console.log('  ' + e.code + ' ' + e.name + ' ' + e.size.toFixed(1) + '亿');
});
