import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))

os.environ.setdefault("AUTO_DJ_DATABASE_DSN", f"sqlite+pysqlite:///{ROOT/'test_auto_dj.db'}")
