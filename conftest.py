"""保证在未安装包的情况下也能直接运行测试（把仓库根目录加入 sys.path）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
