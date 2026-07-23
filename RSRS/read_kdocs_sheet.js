// read_kdocs_sheet.js
// 用 Node.js 直接调用 mcporter 读取 Kdocs 表格

const { execSync } = require('child_process');
const fs = require('fs');

const fileId = 'pg1M6VbERxMqL5rD12mJrxfWeTUWv4g2z';
const driveId = '1077890674';

// 先获取所有工作表信息
console.log('获取工作表列表...\n');

const sheetInfoArgs = JSON.stringify({
  file_id: fileId,
  drive_id: driveId
});

try {
  const result = execSync(
    `"D:\\Program Files\\QClaw\\v0.2.29.592\\resources\\node\\node.exe" ` +
    `"C:\\Users\\沈强\\AppData\\Roaming\\QClaw\\npm-global\\node_modules\\mcporter\\dist\\cli.js" ` +
    `call kdocs-qclaw sheet.get_sheet_info --args '${sheetInfoArgs}'`,
    { encoding: 'utf-8', shell: true }
  );
  console.log(result);
} catch (e) {
  console.error('Error:', e.message);
  console.error('stdout:', e.stdout);
  console.error('stderr:', e.stderr);
}
