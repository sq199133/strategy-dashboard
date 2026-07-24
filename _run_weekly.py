"""Fix: run cmd_sync_weekly with UTF-8 stdout"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
exec(open("D:/QClaw_Trading/maintain_etf_data.py", "r", encoding="utf-8").read())
