// read_kdocs_table_v3.js
// 正确读取Kdocs表格数据 - 最终版

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
      try {
        return JSON.parse(stdout);
      } catch (e2) {}
    }
    return null;
  }
}

console.log('=== 步骤1: 获取工作表列表 ===\n');

const sheetInfo = callMCP('kdocs-qclaw', 'sheet.get_sheets_info', {
  file_id: FILE_ID,
  drive_id: DRIVE_ID
});

if (sheetInfo && sheetInfo.code === 0 && sheetInfo.data && sheetInfo.data.code === 0) {
  const sheets = sheetInfo.data.detail.sheetsInfo;
  
  console.log(`找到 ${sheets.length} 个工作表:\n`);
  sheets.forEach(s => {
    console.log(`  [${s.sheetIdx}] ${s.sheetName} (sheetId: ${s.sheetId})`);
  });
  
  // 找名叫 "RSRS" 的工作表
  const targetSheet = sheets.find(s => s.sheetName === 'RSRS');
  
  if (targetSheet) {
    console.log(`\n=== 步骤2: 读取工作表 "${targetSheet.sheetName}" (sheetId: ${targetSheet.sheetId}) ===\n`);
    
    const data = callMCP('kdocs-qclaw', 'sheet.get_range_data', {
      file_id: FILE_ID,
      drive_id: DRIVE_ID,
      sheetId: targetSheet.sheetId,
      range: 'A1:J200'
    });
    
    if (data && data.code === 0) {
      const rangeData = data.data.detail;
      
      console.log('读取成功！\n');
      
      // 解析并打印表格数据
      if (rangeData && rangeData.values) {
        console.log('表格内容:');
        rangeData.values.forEach((row, idx) => {
          console.log(`第${idx+1}行:`, row);
        });
        
        // 保存到文件
        fs.writeFileSync(
          'D:\\QClaw_Trading\\RSRS\\kdocs_rsrs_sheet.json',
          JSON.stringify(rangeData, null, 2)
        );
        console.log('\n✅ 数据已保存到: D:\\QClaw_Trading\\RSRS\\kdocs_rsrs_sheet.json');
        
        // 尝试解析成持仓记录
        console.log('\n=== 持仓记录解析 ===\n');
        if (rangeData.values.length > 1) {
          // 假设第一行是表头
          const headers = rangeData.values[0];
          console.log('表头:', headers);
          console.log('\n数据行:');
          for (let i = 1; i < rangeData.values.length; i++) {
            const row = rangeData.values[i];
            if (row.some(cell => cell !== '' && cell !== null)) {
              console.log(`  行${i+1}:`, row);
            }
          }
        }
      } else {
        console.log('未找到数据，完整响应:', JSON.stringify(data, null, 2));
      }
    } else {
      console.error('读取数据失败:', data);
    }
  } else {
    console.log('\n未找到名为 "RSRS" 的工作表');
  }
} else {
  console.error('获取工作表列表失败');
  console.error('响应:', JSON.stringify(sheetInfo, null, 2));
}
