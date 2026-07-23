// Fetch today's (4/17) daily returns for benchmark indices
async function main() {
  const indices = [
    {code:'sh000001', name:'上证指数'},
    {code:'sz399006', name:'创业板指'},
    {code:'sh000300', name:'沪深300'},
    {code:'sz399001', name:'深证成指'},
    {code:'sh000688', name:'科创50'},
    {code:'sh000016', name:'上证50'},
    {code:'sh000905', name:'中证500'},
    {code:'sh000852', name:'中证1000'},
    {code:'hkHSI',    name:'恒生指数'},
    {code:'hkHSTECH', name:'恒生科技'},
  ];
  // Get last 2 days of data
  for (const idx of indices) {
    const url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + idx.code + ',day,,,5,qfq';
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(8000) });
      const j = await r.json();
      const arr = j.data && j.data[idx.code] ? (j.data[idx.code].qfqday || j.data[idx.code].day || []) : [];
      if (arr.length >= 2) {
        const today = arr[arr.length-1];
        const yesterday = arr[arr.length-2];
        const dayPct = ((+today[2] - +yesterday[2]) / +yesterday[2] * 100).toFixed(2);
        console.log(idx.name + ': 昨收=' + yesterday[2] + ' 今收=' + today[2] + ' 日涨幅=' + dayPct + '%');
      } else {
        console.log(idx.name + ': 数据不足');
      }
    } catch(e) {
      console.log(idx.name + ': 获取失败');
    }
    await new Promise(r => setTimeout(r, 300));
  }
}
main();
