// Fetch 4/17 opening prices for the 5 ETFs
async function main() {
  const etfs = [
    {code:'159681',market:'SZ',name:'创业板50ETF'},
    {code:'512770',market:'SH',name:'生物医药ETF'},
    {code:'512220',market:'SH',name:'军工ETF'},
    {code:'516390',market:'SH',name:'新能源汽车ETF'},
    {code:'513100',market:'SH',name:'纳指100ETF'}
  ];

  for (const etf of etfs) {
    const secid = etf.market === 'SZ' ? 'sz' + etf.code : 'sh' + etf.code;
    const url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + secid + ',day,,,5,qfq';
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(8000) });
      const j = await r.json();
      const arr = j.data && j.data[secid] ? (j.data[secid].qfqday || j.data[secid].day || []) : [];
      // Find 2026-04-17
      const today = arr.find(k => k[0] === '2026-04-17');
      if (today) {
        console.log(etf.name + '(' + etf.code + '): 日期=' + today[0] + ' 开盘=' + today[1] + ' 收盘=' + today[2] + ' 最高=' + today[3] + ' 最低=' + today[4]);
      } else {
        console.log(etf.name + '(' + etf.code + '): 未找到4/17数据, 最近数据:');
        arr.slice(-3).forEach(k => console.log('  ' + k[0] + ' 开=' + k[1] + ' 收=' + k[2]));
      }
    } catch(e) {
      console.log(etf.name + ': 获取失败 ' + e.message);
    }
    await new Promise(r => setTimeout(r, 300));
  }
}
main();
