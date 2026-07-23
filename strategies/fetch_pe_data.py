# -*- coding: utf-8 -*-
"""
获取指数PE估值数据
使用akshare免费接口获取历史估值数据
"""

import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime
import time
import sys

# 设置输出编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 创建数据目录
PE_DATA_DIR = "D:/QClaw_Trading/data/pe_data"
os.makedirs(PE_DATA_DIR, exist_ok=True)

# 需要获取的指数列表
# 格式: (完整代码, 名称, akshare代码)
INDICES = [
    ("sh000300", "沪深300", "000300"),
    ("sh000905", "中证500", "000905"),
    ("sh000852", "中证1000", "000852"),
    ("sh000688", "科创50", "000688"),
    ("sz399006", "创业板指", "399006"),
    ("sh000016", "上证50", "000016"),
]

def fetch_index_pe_legulegu(index_code: str, index_name: str) -> pd.DataFrame:
    """
    从乐咕乐股获取指数PE数据
    
    Args:
        index_code: 指数代码（如 '000300'）
        index_name: 指数名称
        
    Returns:
        DataFrame with columns: date, pe, pb
    """
    print(f"  正在获取 {index_name} ({index_code}) 数据...")
    
    try:
        # 使用akshare的乐咕乐股接口
        df = ak.stock_a_pe_and_pb_lg(symbol=index_code)
        
        if df is not None and len(df) > 0:
            print(f"  [OK] 获取成功，共 {len(df)} 条记录")
            return df
        else:
            print(f"  [FAIL] 无数据返回")
            return None
            
    except Exception as e:
        print(f"  [FAIL] 获取失败: {str(e)}")
        return None


def fetch_index_pe_funddb(index_code: str, index_name: str) -> pd.DataFrame:
    """
    从基金数据库获取指数估值数据
    
    Args:
        index_code: 指数代码
        index_name: 指数名称
        
    Returns:
        DataFrame with columns: date, pe, pb
    """
    print(f"  正在获取 {index_name} ({index_code}) 数据（funddb）...")
    
    try:
        # index_value_hist_funddb: 指数估值历史数据
        df = ak.index_value_hist_funddb(symbol=index_code)
        
        if df is not None and len(df) > 0:
            print(f"  [OK] 获取成功，共 {len(df)} 条记录")
            return df
        else:
            print(f"  [FAIL] 无数据返回")
            return None
            
    except Exception as e:
        print(f"  [FAIL] 获取失败: {str(e)}")
        return None


def save_pe_data(df: pd.DataFrame, output_file: str, index_name: str):
    """
    保存PE数据到JSON文件
    
    Args:
        df: PE数据DataFrame
        output_file: 输出文件路径
        index_name: 指数名称
    """
    if df is None or len(df) == 0:
        return
    
    # 标准化列名（小写）
    df_clean = df.copy()
    df_clean.columns = [col.lower() for col in df_clean.columns]
    
    # 确保日期格式正确
    if 'date' in df_clean.columns:
        if df_clean['date'].dtype == 'object':
            df_clean['date'] = pd.to_datetime(df_clean['date']).dt.strftime('%Y-%m-%d')
        else:
            df_clean['date'] = pd.to_datetime(df_clean['date']).dt.strftime('%Y-%m-%d')
    
    # 按日期排序
    if 'date' in df_clean.columns:
        df_clean = df_clean.sort_values('date')
    
    # 只保留需要的列
    keep_cols = ['date', 'pe', 'pb']
    available_cols = [col for col in keep_cols if col in df_clean.columns]
    df_clean = df_clean[available_cols]
    
    # 转换为字典列表
    records = df_clean.to_dict('records')
    
    # 保存JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    
    print(f"  [OK] 已保存到: {output_file}")
    print(f"    时间范围: {df_clean['date'].iloc[0]} 至 {df_clean['date'].iloc[-1]}")


def main():
    """主程序"""
    print("=" * 60)
    print("获取指数PE估值数据")
    print("=" * 60)
    print()
    
    # 先尝试一个指数测试接口
    print("测试接口可用性...")
    test_df = None
    use_method = None
    
    # 尝试乐咕乐股接口
    try:
        print("\n尝试乐咕乐股接口...")
        test_df = fetch_index_pe_legulegu("000300", "沪深300")
        if test_df is not None:
            use_method = "legulegu"
    except Exception as e:
        print(f"乐咕乐股接口失败: {e}")
        
    # 如果乐咕乐股失败，尝试funddb
    if test_df is None:
        try:
            print("\n尝试funddb接口...")
            test_df = fetch_index_pe_funddb("000300", "沪深300")
            if test_df is not None:
                use_method = "funddb"
        except Exception as e:
            print(f"funddb接口失败: {e}")
    
    if test_df is None:
        print("\n[FAIL] 所有接口均不可用")
        print("\n可能的解决方案:")
        print("1. 检查网络连接")
        print("2. 访问乐咕乐股网站手动下载: https://legulegu.com/stockdata/market-pe")
        print("3. 等待一段时间后重试（可能有访问限制）")
        return
    
    print(f"\n[OK] 使用 {use_method} 接口")
    print()
    
    # 保存测试数据
    save_pe_data(test_df, 
                 os.path.join(PE_DATA_DIR, "sh000300_pe.json"),
                 "沪深300")
    
    # 获取其他指数
    for full_code, name, code in INDICES[1:]:
        print()
        
        # 等待一下避免请求过快
        time.sleep(2)
        
        if use_method == "legulegu":
            df = fetch_index_pe_legulegu(code, name)
        else:
            df = fetch_index_pe_funddb(code, name)
        
        if df is not None:
            output_file = os.path.join(PE_DATA_DIR, f"{full_code}_pe.json")
            save_pe_data(df, output_file, name)
    
    print()
    print("=" * 60)
    print("数据获取完成")
    print("=" * 60)
    print(f"\n数据目录: {PE_DATA_DIR}")
    print("\n获取的数据文件:")
    for file in os.listdir(PE_DATA_DIR):
        if file.endswith('_pe.json'):
            filepath = os.path.join(PE_DATA_DIR, file)
            size = os.path.getsize(filepath)
            print(f"  - {file} ({size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
