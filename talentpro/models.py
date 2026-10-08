"""跨模块共用的数据模型：检查结果、日志分析结果、差异项。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """检查结果的严重级别。"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def label(self) -> str:
        """定宽标签，便于终端对齐输出。"""
        return {"error": "ERROR", "warning": "WARN ", "info": "INFO "}[self.value]


@dataclass(frozen=True)
class RuleResult:
    """单条规则的一次判定结果。

    只有 ``ERROR`` 会阻断检查通过；``WARNING`` / ``INFO`` 用于提示与展示。
    """

    rule_id: str
    severity: Severity
    message: str
    hint: str = ""

    @property
    def ok(self) -> bool:
        return self.severity is not Severity.ERROR

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "hint": self.hint,
        }


@dataclass
class CheckReport:
    """一次完整检查的聚合结果。"""

    results: list[RuleResult] = field(default_factory=list)

    def add(self, *results: RuleResult) -> None:
        self.results.extend(results)

    def extend(self, results: list[RuleResult]) -> None:
        self.results.extend(results)

    @property
    def errors(self) -> list[RuleResult]:
        return [r for r in self.results if r.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[RuleResult]:
        return [r for r in self.results if r.severity is Severity.WARNING]

    @property
    def infos(self) -> list[RuleResult]:
        return [r for r in self.results if r.severity is Severity.INFO]

    @property
    def passed(self) -> bool:
        return not self.errors

    def of(self, rule_id: str) -> list[RuleResult]:
        """取出指定规则的全部结果。"""
        return [r for r in self.results if r.rule_id == rule_id]

    @property
    def rule_ids(self) -> set[str]:
        return {r.rule_id for r in self.results}

    @property
    def failed_rule_ids(self) -> set[str]:
        return {r.rule_id for r in self.errors}

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "results": [r.to_dict() for r in self.results],
        }

    def summary(self) -> str:
        state = "通过" if self.passed else "未通过"
        return f"{state}：{len(self.errors)} 个错误 / {len(self.warnings)} 个警告"


@dataclass(frozen=True)
class Analysis:
    """一份访问日志的统计结果。"""

    ip_counts: Mapping[str, int]
    status_counts: Mapping[str, int]
    top_ip: str
    top_count: int

    @property
    def total_requests(self) -> int:
        return sum(self.ip_counts.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "top_ip": self.top_ip,
            "top_count": self.top_count,
            "ip_counts": dict(self.ip_counts),
            "status_counts": dict(self.status_counts),
        }


@dataclass(frozen=True)
class Mismatch:
    """期望报告与实际报告之间的一处差异。"""

    kind: str
    section: str
    line: str | None = None

    def describe(self) -> str:
        mapping = {
            "missing_section": f"缺少区块：{self.section}",
            "missing_line": f"区块 {self.section} 缺少行：{self.line}",
            "extra_line": f"区块 {self.section} 多出未预期的行：{self.line}",
        }
        return mapping.get(self.kind, f"{self.kind} @ {self.section}: {self.line}")

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "section": self.section, "line": self.line}
