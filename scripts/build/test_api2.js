// Use fetch (not https module) which worked before
async function main() {
  const url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:MK0021&fields=f12,f13,f14,f2,f3,f6,f20';
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(15000) });
    const j = await r.json();
    console.log('Total:', j.data.total);
    if (j.data.diff) {
      j.data.diff.forEach(d => console.log(d.f12, d.f14, '规模:', (d.f20/1e8).toFixed(1) + '亿'));
    }
  } catch(e) {
    console.log('Error:', e.message);
  }
}
main();
