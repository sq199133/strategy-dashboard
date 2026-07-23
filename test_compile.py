import sys, traceback
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
try:
    import py_compile
    py_compile.compile('D:/Qclaw_Trading/weekly_scan_v4.py', doraise=True)
    print('Compile OK')
except Exception:
    traceback.print_exc()
