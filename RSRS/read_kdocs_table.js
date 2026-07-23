// read_kdocs_table.js
// 正确读取Kdocs表格数据

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
    if (e.stdout) console.error('输出:', e.stdout.toString());
    if (e.stderr) console.error('错误:', e.stderr.toString());
    return null;
  }
}

console.log('=== 步骤1: 获取工作表列表 ===\n');

const sheetInfo = callMCP('kdocs-qclaw', 'sheet.get_sheets_info', {
  file_id: FILE_ID,
  drive_id: DRIVE_ID
});

if (sheetInfo && sheetInfo.code === 0) {
  console.log('工作表列表:');
  const sheets = sheetInfo.data.data.sheets;
  sheets.forEach(s => {
    console.log(`  - ${s.sheetName} (sheetId: ${s.sheetId}, type: ${s.sheetType})`);
  });
  
  // 找名叫 "RSRS" 的工作表
  const targetSheet = sheets.find(s => s.sheetName === 'RSRS' || s.sheetName.includes('RSRS'));
  
  if (targetSheet) {
    console.log(`\n=== 步骤2: 读取工作表 "${targetSheet.sheetName}" ===\n`);
    
    const data = callMCP('kdocs-qclaw', 'sheet.get_range_data', {
      file_id: FILE_ID,
      drive_id: DRIVE_ID,
      sheet_id: targetSheet.sheetId,
      range: 'A1:J100'  // 读前100行，A到J列
    });
    
    if (data && data.code === 0) {
      console.log('读取成功！数据:');
      console.log(JSON.stringify(data.data.data, null, 2));
      
      // 保存到文件
      fs.writeFileSync(
        'D:\\QClaw_Trading\\RSRS\\kdocs_data.json',
        JSON.stringify(data.data.data, null, 2)
      );
      console.log('\n数据已保存到: D:\\QClaw_Trading\\RSRS\\kdocs_data.json');
    } else {
      console.error('读取数据失败:', data);
    }
  } else {
    console.log('\n未找到名为 "RSRS" 的工作表，尝试读取第一个工作表...');
    
    const firstSheet = sheets[0];
    console.log(`读取工作表: ${firstSheet.sheetName}`);
    
    const data = callMCP('kdocs-qclaw', 'sheet.get_range_data', {
      file_id: FILE_ID,
      drive_id: DRIVE_ID,
      sheet_id: firstSheet.sheetId,
      range: 'A1:J100'
    });
    
    if (data && data.code === 0) {
      console.log('读取成功！数据:');
      console.log(JSON.stringify(data.data.data, null, 2));
    }
  }
} else {
  console.error('获取工作表列表失败:', sheetInfo);
}
