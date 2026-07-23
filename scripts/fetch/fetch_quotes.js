const https = require('https');

const codes = ['159681', '512770', '512220', '516390', '513100'];

async function fetchQuote(code) {
  return new Promise((resolve) => {
    // 新浪财经接口格式
    const market = code.startsWith('6') ? 'sh' : 'sz';
    // 使用腾讯接口
    const url = `https://qt.gtimg.cn/q=${market}${code}`;
    
    https.get(url, (res) => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          console.log(`Raw response for ${code}:`, data.substring(0, 200));
          // 格式: v_sz159681="51~创业板50~1.729~..."
          const match = data.match(/v_[^=]+="([^"]+)"/);
          if (match) {
            const parts = match[1].split('~');
            resolve({
              code: code,
              name: parts[1] || code,
              price: parseFloat(parts[3]) || 0,
              change: parseFloat(parts[31]) || 0,
              pct: parseFloat(parts[32]) || 0
            });
          } else {
            resolve({ code: code, error: 'No match', raw: data.substring(0, 100) });
          }
        } catch (e) {
          resolve({ code: code, error: e.message });
        }
      });
    }).on('error', (e) => {
      resolve({ code: code, error: e.message });
    });
  });
}

(async () => {
  for (const code of codes) {
    const r = await fetchQuote(code);
    console.log('Result:', JSON.stringify(r));
    await new Promise(r => setTimeout(r, 300)); // 延迟避免限频
  }
})();
