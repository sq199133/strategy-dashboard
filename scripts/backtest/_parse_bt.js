const fs = require('fs');
const buf = fs.readFileSync('D:/QClaw_Trading/scripts/backtest/_bt_out.txt');
const text = buf.toString('latin1');
const lines = text.split('\n').map(l => l.trim()).filter(l => {
  if (!l) return false;
  const pct = (l.match(/%/g) || []).length;
  if (pct >= 10) return false;
  return l.includes('S') || l.includes('回测') || l.includes('夏普') || l.includes('年化') || l.includes('波动率') || l.includes('Top') || l.includes('完整') || l.includes('恒星') || l.includes('纳斯达克') || l.includes('易方达') || l.includes('华夏') || l.includes('广发') || l.includes('华泰') || l.includes('━━') || l.includes('══') || l.includes('基准') || l.includes('胜率') || l.includes('回撤') || l.includes('交易数');
});
console.log(lines.join('\n'));
