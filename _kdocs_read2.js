const { execSync } = require('child_process');

const args = {
  file_id: "pg1M6VbERxMqL5rD12mJrxfWeTUWv4g2z",
  worksheet_id: 3,
  sheetId: 3,
  range: { rowFrom: 0, rowTo: 9, colFrom: 0, colTo: 6 }
};

const argsStr = JSON.stringify(args);

try {
  const result = execSync(
    `mcporter call kdocs-qclaw sheet.get_range_data --args "${argsStr.replace(/"/g, '\\"')}"`,
    { encoding: 'utf-8', timeout: 30000 }
  );
  console.log(result);
} catch (e) {
  console.error('STDERR:', e.stderr);
  if (e.stdout) console.error('STDOUT:', e.stdout);
}
