# -*- coding: utf-8 -*-
"""
PE数据获取总结和手动导入工具

已获取的数据：
- A股市场整体PE: D:/QClaw_Trading/data/pe_data/a_market_pe.json

未获取的数据：
- 沪深300 PE
- 中证500 PE
- 中证1000 PE
- 科创50 PE
- 创业板指 PE

获取方法：
"""

import pandas as pd
import json
import os

PE_DATA_DIR = 'D:/QClaw_Trading/data/pe_data'

def check_available_data():
    """检查已有的PE数据"""
    print("=" * 60)
    print("已有PE数据文件")
    print("=" * 60)

    if not os.path.exists(PE_DATA_DIR):
        print("数据目录不存在")
        return

    files = [f for f in os.listdir(PE_DATA_DIR) if f.endswith('.json')]
    for f in files:
        filepath = os.path.join(PE_DATA_DIR, f)
        size = os.path.getsize(filepath) / 1024

        with open(filepath, 'r', encoding='utf-8') as file:
            data = json.load(file)

        if len(data) > 0:
            first_date = data[0].get('date', 'N/A')
            last_date = data[-1].get('date', 'N/A')
            count = len(data)
            print(f"\n{f}")
            print(f"  大小: {size:.1f} KB")
            print(f"  记录: {count} 条")
            print(f"  时间: {first_date} 至 {last_date}")

            # 显示最新PE值
            if 'pe' in data[-1]:
                latest_pe = data[-1]['pe']
                print(f"  最新PE: {latest_pe:.2f}")

def show_market_pe_stats():
    """显示市场整体PE统计"""
    filepath = os.path.join(PE_DATA_DIR, 'a_market_pe.json')

    if not os.path.exists(filepath):
        print("市场PE数据不存在")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df['pe'] = pd.to_numeric(df['pe'], errors='coerce')

    # 计算分位
    current_pe = df['pe'].iloc[-1]
    percentile = (df['pe'] <= current_pe).sum() / len(df) * 100

    print("\n" + "=" * 60)
    print("A股市场整体PE分析")
    print("=" * 60)
    print(f"\n当前PE: {current_pe:.2f}")
    print(f"历史分位: {percentile:.1f}%")
    print(f"平均值: {df['pe'].mean():.2f}")
    print(f"中位数: {df['pe'].median():.2f}")
    print(f"标准差: {df['pe'].std():.2f}")
    print(f"最小值: {df['pe'].min():.2f}")
    print(f"最大值: {df['pe'].max():.2f}")

    # 分位阈值
    print(f"\n估值区间:")
    print(f"  10%分位: {df['pe'].quantile(0.1):.2f}  <- 极低估值（强买）")
    print(f"  20%分位: {df['pe'].quantile(0.2):.2f}  <- 低估值（买入）")
    print(f"  50%分位: {df['pe'].quantile(0.5):.2f}  <- 中性")
    print(f"  80%分位: {df['pe'].quantile(0.8):.2f}  <- 高估值（卖出）")
    print(f"  90%分位: {df['pe'].quantile(0.9):.2f}  <- 极高估值（强卖）")

    # 建议仓位
    if percentile <= 10:
        position = "100%（满仓）"
    elif percentile <= 20:
        position = "80%"
    elif percentile <= 50:
        position = "50%"
    elif percentile <= 80:
        position = "20%"
    elif percentile <= 90:
        position = "10%"
    else:
        position = "0%（空仓）"

    print(f"\n当前建议仓位: {position}")

def show_data_sources():
    """显示数据获取方法"""
    print("\n" + "=" * 60)
    print("获取特定指数PE数据的方法")
    print("=" * 60)

    print("""
方法一：乐咕乐股网站（推荐）
网址: https://legulegu.com/stockdata/market-pe
步骤:
  1. 打开网站
  2. 选择指数（如沪深300）
  3. 点击"导出数据"按钮
  4. 保存为JSON格式

方法二：中证指数公司官网
网址: https://www.csindex.com.cn/zh-CN/indices/index-list
步骤:
  1. 打开官网
  2. 搜索指数
  3. 查看"估值数据"
  4. 导出数据

方法三：注册tushare获取API
网址: https://tushare.pro/
步骤:
  1. 注册账号
  2. 获取token
  3. 使用index_dailybasic接口获取PE数据

方法四：东方财富Choice终端
需要购买终端，提供完整估值数据
""")

def import_pe_data(input_file, index_code):
    """导入PE数据

    Args:
        input_file: CSV或JSON文件路径
        index_code: 指数代码（如 'sh000300'）
    """
    if input_file.endswith('.csv'):
        df = pd.read_csv(input_file)
    elif input_file.endswith('.json'):
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = pd.DataFrame(data)
    else:
        print("Unsupported file format")
        return

    # 标准化列名
    column_mapping = {
        '日期': 'date',
        'date': 'date',
        '市盈率': 'pe',
        'PE': 'pe',
        'pe': 'pe',
        '市净率': 'pb',
        'PB': 'pb',
        'pb': 'pb'
    }

    df.columns = [column_mapping.get(col, col) for col in df.columns]

    # 只保留需要的列
    keep_cols = [col for col in ['date', 'pe', 'pb'] if col in df.columns]
    df = df[keep_cols]

    # 格式化日期
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

    # 保存
    output_file = os.path.join(PE_DATA_DIR, f'{index_code}_pe.json')
    records = df.to_dict('records')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"已导入: {output_file}")
    print(f"记录数: {len(df)}")


if __name__ == "__main__":
    check_available_data()
    show_market_pe_stats()
    show_data_sources()

    print("\n" + "=" * 60)
    print("下一步操作")
    print("=" * 60)
    print("""
1. 访问乐咕乐股网站下载特定指数PE数据
2. 将数据文件放到 D:/QClaw_Trading/data/pe_data/ 目录
3. 运行回测脚本验证策略效果

当前已有市场整体PE数据，可以先用这个数据开发策略。
""")
