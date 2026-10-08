"""题目级与仓库级校验规则。

导入本包即完成规则注册（各规则模块在被导入时通过 ``@rule`` 装饰器注册）。
"""

from __future__ import annotations

# 导入即注册
from . import (  # noqa: E402,F401
    consistency,
    instruction,
    metadata,
    report_contract,
    security,
    structure,
)
from .base import (
    RegisteredRule,
    categories,
    finding,
    registered_rules,
    rule,
    run_checks,
)
from .repo import check_repository
from .security import scan_secrets

__all__ = [
    "RegisteredRule",
    "categories",
    "check_repository",
    "finding",
    "registered_rules",
    "rule",
    "run_checks",
    "scan_secrets",
]
