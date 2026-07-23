const https = require('https');

// 查询代码信息
const codes = ['006195', '539003'];

async function query(code) {
  return new Promise((resolve) => {
    // 尝试两个市场
    const markets = ['sh', 'sz'];
    let found = false;
    
    Promise.all(markets.map(m => {
      return new Promise((res) => {
        const url = `https://qt.gtimg.cn/q=${m}${code}`;
        https.get(url, (response) => {
          let data = '';
          response.on('data', (chunk) => data += chunk);
          response.on('end', () => {
            const match = data.match(/v_[^=]+="([^"]+)"/);
            if (match && !data.includes('pv_none_match')) {
              const parts = match[1].split('~');
              if (parts.length > 3) {
                res({ code, name: parts[1], price: parts[3], market: m });
                found = true;
              }
            }
            res(null);
          });
        }).on('error', () => res(null));
      });
    })).then(results => {
      const found = results.find(r => r !== null);
      resolve(found || { code, error: 'not found' });
    });
  });
}

(async () => {
  for (const c of codes) {
    const r = await query(c);
    console.log(JSON.stringify(r));
  }
})();
