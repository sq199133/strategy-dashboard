// read_kdocs_table_v2.js
// 正确读取Kdocs表格数据 - 修复版

const { execSync } = require('child_process');
const fs = require('fs');

const FILE_ID = 'pg1M6VbERxMqL5rD12mJrxfWeTUWv4g2z';
const DRIVE_ID = '1077890674';
const NODE_EXE = 'D:\\Program Files\\QClaw\\v0.2.29.592\\resources\\node\\node.exe';
const MCPORTER_JS = 'C:\\Users\\沈强\\AppData\\Roaming\\QClaw\\npm-global\\node_modules\\mcporter\\dist\\cli.js';

function callMCP(service, tool, args) {
  const argsJson = JSON.stringify(args);
  const cmd = `"${NODE_EXE}" "${MCPORTER_JS}" call ${service} ${tool} --args ${JSON.stringify(argsJson)}`;
  
  try {
    const result = execSync(cmd, { encoding: 'utf-8', shell: true, maxBuffer: 10 * 1024 * 1024 });
    return JSON.parse(result);
  } catch (e) {
    console.error('调用失败:', e.message);
    if (e.stdout) {
      const stdout = e.stdout.toString();
      console.error('输出:', stdout);
      // 尝试从错误输出中解析JSON
      try {
        return JSON.parse(stdout);
      } catch (e2) {
        // 忽略
      }
    }
    if (e.stderr) console.error('错误:', e.stderr.toString());
    return null;
  }
}

console.log('=== 步骤1: 获取工作表列表 ===\n');

const sheetInfo = callMCP('kdocs-qclaw', 'sheet.get_sheets_info', {
  file_id: FILE_ID,
  drive_id: DRIVE_ID
});

console.log('完整响应:');
console.log(JSON.stringify(sheetInfo, null, 2));

if (sheetInfo && sheetInfo.code === 0 && sheetInfo.data && sheetInfo.data.code === 0) {
  const data = sheetInfo.data.data;
  console.log('\n工作表列表:');
  
  // 尝试不同的字段名
  const sheets = data.sheets || data.worksheets || [];
  
  if (sheets.length === 0) {
    console.log('未找到工作表，响应数据结构:', Object.keys(data));
  } else {
    sheets.forEach(s => {
      console.log(`  - ${s.sheetName || s.name} (sheetId: ${s.sheetId || s.id}, type: ${s.sheetType || s.type})`);
    });
    
    // 找名叫 "RSRS" 的工作表
    const targetSheet = sheets.find(s => (s.sheetName || s.name) === 'RSRS' || (s.sheetName || s.name).includes('RSRS'));
    
    if (targetSheet) {
      const sheetId = targetSheet.sheetId || targetSheet.id;
      const sheetName = targetSheet.sheetName || targetSheet.name;
      console.log(`\n=== 步骤2: 读取工作表 "${sheetName}" (sheetId: ${sheetId}) ===\n`);
      
      const data = callMCP('kdocs-qclaw', 'sheet.get_range_data', {
        file_id: FILE_ID,
        drive_id: DRIVE_ID,
        sheetId: sheetId,
        range: 'A1:J100'
      });
      
      if (data && data.code === 0) {
        console.log('读取成功！数据:');
        console.log(JSON.stringify(data.data, null, 2));
        
        // 保存到文件
        fs.writeFileSync(
          'D:\\QClaw_Trading\\RSRS\\kdocs_data.json',
          JSON.stringify(data.data, null, 2)
        );
        console.log('\n数据已保存到: D:\\QClaw_Trading\\RSRS\\kdocs_data.json');
      } else {
        console.error('读取数据失败:', data);
      }
    }
  }
} else {
  console.error('获取工作表列表失败');
}
