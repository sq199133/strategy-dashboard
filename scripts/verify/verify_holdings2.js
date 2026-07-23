// Fetch fund data using built-in fetch
async function fetchFund(code, market) {
  const secid = market === 'SZ' ? '0.' + code : '1.' + code;
  const url = `https://push2.eastmoney.com/api/qt/stock/get?secid=${secid}&fields=f57,f58,f84,f100`;
  const r = await fetch(url, { signal: AbortSignal.timeout(8000) });
  return await r.json();
}

async function main() {
  const toCheck = [
    {code:'513100', m:'SH'}, {code:'513500', m:'SH'}, {code:'513030', m:'SH'},
    {code:'512770', m:'SH'}, {code:'512290', m:'SH'}, {code:'159938', m:'SZ'},
    {code:'512220', m:'SH'}, {code:'512660', m:'SH'}, {code:'512680', m:'SH'},
    {code:'516390', m:'SH'}, {code:'515700', m:'SH'}, {code:'513090', m:'SH'},
    {code:'513520', m:'SH'}, {code:'512500', m:'SH'}, {code:'512100', m:'SH'},
  ];
  for (const item of toCheck) {
    try {
      const j = await fetchFund(item.code, item.m);
      if (j && j.data) {
        const d = j.data;
        console.log(item.code + ' ' + d.f58 + ' | ' + (d.f84 ? (d.f84/1e8).toFixed(1)+'亿':'N/A'));
      } else {
        console.log(item.code + ' | 无数据');
      }
    } catch(e) { console.log(item.code + ' | 错误:' + e.message); }
    await new Promise(r => setTimeout(r, 200));
  }
}
main();
