"""CLI入口
用法:
  python -m qclaw_stock_data kline 159928 50
  python -m qclaw_stock_data quote 159928
  python -m qclaw_stock_data status
  python -m qclaw_stock_data cache clean
"""
import sys
import argparse
import json
from .fetcher import DataFetcher


def cmd_kline(args):
    f = DataFetcher()
    records = f.kline(args.code, datalen=args.datalen, period=args.period)
    if not records:
        print(f"获取失败: {args.code}")
        return 1
    print(f"=== {args.code} {args.period} K线 (最近{len(records)}条) ===")
    for r in records[-min(args.show, len(records)):]:
        print(f"  {r['date']} O:{r['open']:.4f} H:{r['high']:.4f} L:{r['low']:.4f} C:{r['close']:.4f} V:{r['vol']}")
    return 0


def cmd_quote(args):
    f = DataFetcher()
    q = f.quote(args.code)
    if not q:
        print(f"获取失败: {args.code}")
        return 1
    print(f"=== {q.get('name', args.code)} 实时行情 ===")
    print(f"  现价: {q.get('price','?')}  开: {q.get('open','?')}  高: {q.get('high','?')}  低: {q.get('low','?')}")
    print(f"  昨收: {q.get('prev_close','?')}  量: {q.get('volume','?')}  额: {q.get('amount','?')}")
    print(f"  时间: {q.get('date','?')} {q.get('time','?')}")
    return 0


def cmd_status(args):
    f = DataFetcher()
    s = f.status()
    print(json.dumps(s, ensure_ascii=False, indent=2))
    return 0


def cmd_cache(args):
    f = DataFetcher()
    if args.action == "stats":
        print(json.dumps(f.cache.stats(), indent=2))
    elif args.action == "clean":
        n = f.cache.clear_expired()
        print(f"清理 {n} 条过期缓存")
    return 0


def main():
    parser = argparse.ArgumentParser(description="qclaw_stock_data - A股数据SDK")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("kline", help="K线数据")
    p.add_argument("code")
    p.add_argument("datalen", type=int, nargs="?", default=50)
    p.add_argument("--period", default="daily", choices=["daily","weekly","monthly"])
    p.add_argument("--show", type=int, default=10)
    p.set_defaults(func=cmd_kline)

    p = sub.add_parser("quote", help="实时行情")
    p.add_argument("code")
    p.set_defaults(func=cmd_quote)

    p = sub.add_parser("status", help="健康状态")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("cache", help="缓存管理")
    p.add_argument("action", choices=["stats", "clean"])
    p.set_defaults(func=cmd_cache)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
