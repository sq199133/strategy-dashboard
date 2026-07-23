# -*- coding: utf-8 -*-
import sys
print("Python:", sys.version)
try:
    import akshare as ak
    print("akshare:", ak.__version__)
except ImportError:
    print("akshare: NOT INSTALLED")
try:
    import numpy as np
    print("numpy:", np.__version__)
except ImportError:
    print("numpy: NOT INSTALLED")
try:
    import pandas as pd
    print("pandas:", pd.__version__)
except ImportError:
    print("pandas: NOT INSTALLED")
print("READY")
