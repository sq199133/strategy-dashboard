"""代码市场识别 - A股ETF/股票"""
def code_market(code: str) -> str:
    """A股代码识别市场

    沪市:
      - 6xxxxx 主板/科创板
      - 5xxxxx ETF/封闭基金
      - 9xxxxx B股
    深市:
      - 0xxxxx 主板
      - 3xxxxx 创业板
      - 1xxxxx 中小板/基金/债券
      - 2xxxxx B股
      - 15xxxx LOF基金
      - 16xxxx LOF基金
      - 159xxx ETF(深市)
      - 184xxx 债券
    """
    s = str(code).zfill(6)
    # 沪市: 60/68/9/5 开头
    if s.startswith(("60", "68", "9", "5")):
        return "sh"
    # 沪市基金: 1xxxx 中"11"开头是沪市债券, "15xxxx"是深市LOF, "159xxx"是深市ETF
    if s.startswith("11"):
        return "sh"
    # 其他(0, 1, 2, 3, 4, 15, 16, 159) 默认深市
    return "sz"


if __name__ == "__main__":
    test_cases = [
        # (code, expected_market, description)
        ("159928", "sz", "159xxx深市ETF"),
        ("159901", "sz", "159xxx深市ETF"),
        ("510500", "sh", "5xxxxx沪市ETF"),
        ("510050", "sh", "5xxxxx沪市ETF"),
        ("600519", "sh", "6xxxxx沪市主板"),
        ("000001", "sz", "0xxxxx深市主板"),
        ("300750", "sz", "3xxxxx深市创业板"),
        ("002415", "sz", "0xxxxx深市主板"),
        ("688981", "sh", "68xxxx沪市科创板"),
        ("501018", "sh", "5xxxxx沪市LOF"),
        ("161039", "sz", "16xxxx深市LOF"),
        ("163208", "sz", "16xxxx深市LOF"),
        ("588000", "sh", "5xxxxx沪市科创ETF"),
        ("159792", "sz", "159xxx深市ETF"),
        ("110011", "sh", "11xxxx沪市债券"),
    ]
    print("代码市场识别测试:")
    fail = 0
    for code, expected, desc in test_cases:
        actual = code_market(code)
        status = "✓" if actual == expected else "❌"
        if actual != expected:
            fail += 1
        print(f"  {status} {code} -> {actual} (期望:{expected}) {desc}")
    print(f"\n{len(test_cases)-fail}/{len(test_cases)} 通过")
