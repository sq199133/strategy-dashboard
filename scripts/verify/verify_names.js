// Verify actual fund names for codes in our pool
async function main() {
  const codes = [
    {code:'512770',market:'SH'}, {code:'512220',market:'SH'},
    {code:'159681',market:'SZ'}, {code:'516390',market:'SH'}, {code:'513100',market:'SH'},
    // Also check potential correct codes for 生物医药 and 军工
    {code:'512290',market:'SH'}, // possible 生物医药 code
    {code:'512660',market:'SH'}, // possible 军工 code
    {code:'512810',market:'SH'}, // another possible 军工 code
  ];
  
  for (const item of codes) {
    const secid = item.market === 'SZ' ? '0.' + item.code : '1.' + item.code;
    const url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=' + secid + '&fields=f57,f58,f84';
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(8000) });
      const j = await r.json();
      const d = j.data;
      if (d) {
        console.log(item.code + ' → ' + d.f58 + ' (市值: ' + (d.f84 ? (d.f84/1e8).toFixed(1) + '亿' : 'N/A') + ')');
      } else {
        console.log(item.code + ' → 无数据');
      }
    } catch(e) {
      console.log(item.code + ' → 获取失败');
    }
    await new Promise(r => setTimeout(r, 200));
  }
}
main();
