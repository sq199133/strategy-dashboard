import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

fp = r'D:\Qclaw_Trading\backtest_v5_qual_sizer.py'
text = open(fp, 'r', encoding='utf-8').read()

# 1. Add score-mode args after mom3w-threshold
old1 = "ap.add_argument('--mom3w-threshold', type=float, default=0.0)"
new1 = old1 + "\n    ap.add_argument('--score-mode', type=str, default='lb3', choices=['lb3','composite'])\n    ap.add_argument('--score-w1', type=float, default=0.3, help='mom1w weight for composite')\n    ap.add_argument('--score-w3', type=float, default=0.5, help='mom3w weight for composite')"
assert old1 in text, "Cannot find 1"
text = text.replace(old1, new1, 1)

# 2. Add mom1w, mom8w, score to return dict
old2 = "return {'code': code, 'close': price, 'mom': mom, 'dev': dev}"
new2 = "mom1w = cs[-1] / cs[-2] - 1 if len(cs) >= 2 else mom\n        mom8w = cs[-1] / cs[-8] - 1 if len(cs) >= 9 else mom\n        score = mom if args.score_mode == 'lb3' else (args.score_w1 * mom1w + args.score_w3 * mom + (1-args.score_w1-args.score_w3) * mom8w)\n        " + old2[:-1] + ", 'mom1w': mom1w, 'mom8w': mom8w, 'score': score}"
assert old2 in text, "Cannot find 2"
text = text.replace(old2, new2, 1)

# 3. Sort by score instead of mom
old3 = "candidates.sort(key=lambda x: x['mom'], reverse=True)"
new3 = "candidates.sort(key=lambda x: x['score'], reverse=True)"
assert old3 in text, "Cannot find 3"
text = text.replace(old3, new3, 1)

# 4. Add score note to label
old4 = "g3_note = f\" M1W{args.mom1w_threshold:+.0f}M3W{args.mom3w_threshold:+.0f}\" if args.mom1w_threshold != -1 or args.mom3w_threshold != 0 else ''\n    label = f\"MA{args.ma_s}/{args.ma_l} {lb_label} D{args.max_dev} H{args.top_n}{g3_note}\""
new4 = "w1, w3 = args.score_w1, args.score_w3\n    g3_note = f\" M1W{args.mom1w_threshold:+.0f}M3W{args.mom3w_threshold:+.0f}\" if abs(args.mom1w_threshold + 1) > 0.01 or abs(args.mom3w_threshold) > 0.01 else ''\n    score_note = f\" SC{int(w1*100):d}{int(w3*100):d}{int(100-w1*100-w3*100):d}\" if args.score_mode == 'composite' else ''\n    label = f\"MA{args.ma_s}/{args.ma_l} {lb_label} D{args.max_dev} H{args.top_n}{score_note}{g3_note}\""
assert old4 in text, "Cannot find 4"
text = text.replace(old4, new4, 1)

open(fp, 'w', encoding='utf-8').write(text)
print("patched OK")
