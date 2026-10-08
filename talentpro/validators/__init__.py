"""题目级与仓库级校验规则。

导入本包即完成规则注册（各规则模块在被导入时通过 ``@rule`` 装饰器注册）。
"""

from __future__ import annotations

from .base import (
    RegisteredRule,
    categories,
    finding,
    registered_rules,
    rule,
    run_checks,
)
from .security import scan_secrets

# 导入即注册
from . import consistency, instruction, metadata, report_contract, security, structure  # noqa: E402,F401

__all__ = [
    "RegisteredRule",
    "categories",
    "finding",
    "registered_rules",
    "rule",
    "run_checks",
    "scan_secrets",
]
