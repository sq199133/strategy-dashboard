const { execSync } = require('child_process');
const url = 'https://www.jijindou.com/etf?current=1&max_scale=1&core_index=1&optcheck=1';
const cmd = `node "D:\\Program Files\\QClaw\\resources\\openclaw\\config\\skills\\xbrowser\\scripts\\xb.cjs" run --browser cft open "${url}"`;
console.log(execSync(cmd, { timeout: 30000 }).toString());
