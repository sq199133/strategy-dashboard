#!/usr/bin/env python3
"""
Agent自我检查脚本
定期检查近期成功率低的问题，生成自查报告
"""

import json
import os
from datetime import datetime, timedelta
import subprocess

def check_recent_logs():
    """检查近期工作日志"""
    memory_dir = r"C:\Users\沈强\.qclaw\workspace\memory"
    issues = []
    
    # 检查最近7天的日志
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        log_file = os.path.join(memory_dir, f"{date}.md")
        
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # 查找错误关键词
                if '失败' in content or '错误' in content or '异常' in content:
                    issues.append({
                        'date': date,
                        'file': log_file,
                        'has_issues': True
                    })
    
    return issues

def check_gateway_status():
    """检查Gateway状态"""
    try:
        result = subprocess.run(
            ['openclaw', 'gateway', 'status'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            'status': 'running' if result.returncode == 0 else 'error',
            'output': result.stdout + result.stderr
        }
    except Exception as e:
        return {
            'status': 'error',
            'output': str(e)
        }

def generate_report():
    """生成自查报告"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'checks': {}
    }
    
    # 检查日志
    print("正在检查近期工作日志...")
    report['checks']['recent_logs'] = check_recent_logs()
    
    # 检查Gateway
    print("正在检查Gateway状态...")
    report['checks']['gateway'] = check_gateway_status()
    
    # 检查ETF池文件
    print("正在检查ETF池文件...")
    etf_pool_path = r"D:\QClaw_Trading\scripts\scan\etf_pool.json"
    if os.path.exists(etf_pool_path):
        try:
            with open(etf_pool_path, 'r', encoding='utf-8') as f:
                etf_pool = json.load(f)
                report['checks']['etf_pool'] = {
                    'status': 'ok',
                    'count': len(etf_pool) if isinstance(etf_pool, list) else 'unknown'
                }
        except Exception as e:
            report['checks']['etf_pool'] = {
                'status': 'error',
                'error': str(e)
            }
    else:
        report['checks']['etf_pool'] = {
            'status': 'missing',
            'path': etf_pool_path
        }
    
    return report

def main():
    """主函数"""
    print(f"{'='*60}")
    print(f"Agent自我检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    report = generate_report()
    
    # 输出报告
    print("\n检查报告:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    # 保存报告
    report_dir = r"D:\QClaw_Trading\scripts\verify\reports"
    os.makedirs(report_dir, exist_ok=True)
    
    report_file = os.path.join(
        report_dir,
        f"self_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n报告已保存至: {report_file}")
    
    # 输出问题摘要
    print(f"\n{'='*60}")
    print("问题摘要:")
    print(f"{'='*60}")
    
    gateway_status = report['checks'].get('gateway', {}).get('status')
    if gateway_status == 'error':
        print("[Warning] Gateway状态异常，需要修复配对问题")
    
    log_issues = report['checks'].get('recent_logs', [])
    if log_issues:
        print(f"[Warning] 发现{len(log_issues)}个日志文件可能存在问题")
    
    etf_pool_status = report['checks'].get('etf_pool', {}).get('status')
    if etf_pool_status != 'ok':
        print(f"[Warning] ETF池文件状态: {etf_pool_status}")
    
    if gateway_status == 'ok' and not log_issues and etf_pool_status == 'ok':
        print("[OK] 所有检查通过")
    
    print(f"\n{'='*60}")

if __name__ == "__main__":
    main()
