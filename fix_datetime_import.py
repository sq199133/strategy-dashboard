#!/usr/bin/env python3
"""Fix datetime import shadowing issue."""
fp = __import__("pathlib").Path("D:/QClaw_Trading/maintain_etf_data.py")
content = fp.read_text(encoding="utf-8")

# 1. Fix top-level import
old_top_import = "import json, sys, time, random, requests, datetime"
new_top_import = 'import json, sys, time, random, requests\nfrom datetime import datetime, date'
content = content.replace(old_top_import, new_top_import)

# 2. Remove all local from-imports that shadow
content = content.replace("\n    from datetime import datetime, date", "")
content = content.replace("\n    from datetime import datetime", "")

# 3. Fix strptime calls: datetime.datetime.strptime -> datetime.strptime
content = content.replace("datetime.datetime.strptime", "datetime.strptime")

# 4. Fix date.today() calls (no change needed, but check)
# datetime.datetime.now() shouldn't be affected since we import datetime class
content = content.replace("datetime.datetime.now()", "datetime.now()")

fp.write_text(content, encoding="utf-8")
print("Done")
