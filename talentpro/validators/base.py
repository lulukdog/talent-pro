"""规则框架：注册、执行与结果聚合。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ..models import CheckReport, RuleResult, Severity
from ..spec import TaskSpec


@dataclass(frozen=True)
class RegisteredRule:
    """一条已注册的规则。"""

    id: str
    title: str
    category: str
    func: Callable[[TaskSpec], list[RuleResult]]


_REGISTRY: list[RegisteredRule] = []


def rule(rule_id: str, title: str, category: str) -> Callable:
    """把一个 ``TaskSpec -> list[RuleResult]`` 函数注册为规则。

    规则函数只需返回「有问题的项」；全部通过时由 :func:`run_checks` 补一条
    ``INFO`` 记录，便于在明细里看到规则确实跑过。
    """

    def decorator(func: Callable[[TaskSpec], list[RuleResult]]) -> Callable[[TaskSpec], list[RuleResult]]:
        _REGISTRY.append(RegisteredRule(id=rule_id, title=title, category=category, func=func))
        return func

    return decorator


def registered_rules(category: str | None = None) -> list[RegisteredRule]:
    """返回已注册规则；``category`` 非空时只返回该分类。"""
    if category is None:
        return list(_REGISTRY)
    return [item for item in _REGISTRY if item.category == category]


def categories() -> list[str]:
    """全部规则分类（保持注册顺序）。"""
    seen: list[str] = []
    for item in _REGISTRY:
        if item.category not in seen:
            seen.append(item.category)
    return seen


def finding(rule_id: str, severity: Severity, message: str, hint: str = "") -> RuleResult:
    """构造一条检查结果。"""
    return RuleResult(rule_id=rule_id, severity=severity, message=message, hint=hint)


def run_checks(
    task: TaskSpec,
    *,
    category: str | None = None,
    rule_ids: Iterable[str] | None = None,
) -> CheckReport:
    """执行规则并汇总结果。

    单条规则抛出异常不会中断整体检查，而是记录为一条 ``ERROR``。
    """
    selected = registered_rules(category)
    if rule_ids is not None:
        wanted = set(rule_ids)
        selected = [item for item in selected if item.id in wanted]

    report = CheckReport()
    for item in selected:
        try:
            results = item.func(task)
        except Exception as exc:  # noqa: BLE001 - 规则异常需要被降级为检查结果
            report.add(
                finding(item.id, Severity.ERROR, f"规则执行异常：{exc.__class__.__name__}: {exc}", "请检查题目文件是否可读、格式是否合法")
            )
            continue

        if results:
            report.extend(results)
        else:
            report.add(finding(item.id, Severity.INFO, f"通过：{item.title}"))

    return report
