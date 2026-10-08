"""后续工作（TODO）清单：由检查结论推导，也可独立维护。

平台第六步要求「填写至少 5 条后续工作」，本模块保证任何题目都能自动生成
不少于 5 条、且与当前检查结论一致的可执行待办。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .models import CheckReport, RuleResult, Severity

MINIMUM_TODOS = 5


@dataclass(frozen=True)
class TodoItem:
    """一条后续工作。"""

    title: str
    rationale: str
    acceptance: str

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "rationale": self.rationale, "acceptance": self.acceptance}


#: 与工具链能力缺口对应的通用待办，按优先级排列。
DEFAULT_TODOS: tuple[TodoItem, ...] = (
    TodoItem(
        title="为题目配置独立判卷环境",
        rationale="当前判卷与做题共用镜像，判卷依赖会暴露给考生，也影响镜像体积。",
        acceptance="task.toml 设置 [verifier] environment_mode = \"separate\"，oracle 测试仍为 reward=1。",
    ),
    TodoItem(
        title="引入 Reward Kit 评分卡，支持部分给分",
        rationale="二值 reward 无法区分「只差一个区块」和「完全没做」，不利于诊断题目质量。",
        acceptance="tests/ 使用 Reward Kit 断言，本地可输出分项得分。",
    ),
    TodoItem(
        title="新增 talentpro oracle 子命令",
        rationale="本地跑 oracle 需要手写较长命令，容易漏参数、漏版本。",
        acceptance="talentpro oracle <task> 自动调用 harbor trials start -a oracle 并汇总 reward。",
    ),
    TodoItem(
        title="建立题库索引文件 tasks.json",
        rationale="题目数量增长后，需要按难度/标签/通过率检索与统计。",
        acceptance="talentpro index 扫描题库目录并生成包含难度、标签、最近判卷结果的索引。",
    ),
    TodoItem(
        title="补充大数据量的性能用例",
        rationale="日志类题目的输入只有数百行，无法覆盖真实规模的性能约束。",
        acceptance="提供 ≥100 万行的生成器与超时基线，Oracle 测试在 600s 内完成。",
    ),
    TodoItem(
        title="为里程碑评审补充人工复核记录",
        rationale="自动划分只能保证覆盖与顺序，独立目标是否成立仍需人工确认。",
        acceptance="docs 下提供评审记录模板，包含目标、验证方式与评审结论。",
    ),
    TodoItem(
        title="把敏感信息扫描接入提交钩子",
        rationale="人工清理容易遗漏，泄漏成本高。",
        acceptance="pre-commit 调用 talentpro check --category security，命中即阻断提交。",
    ),
)

_LEVEL_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def suggest_todos(
    findings: Sequence[RuleResult] | None = None,
    *,
    minimum: int = MINIMUM_TODOS,
    limit: int | None = None,
) -> list[TodoItem]:
    """结合检查结论生成待办，并用通用待办补足 ``minimum`` 条。"""
    items: list[TodoItem] = []

    if findings:
        ordered = sorted(findings, key=lambda item: _LEVEL_ORDER[item.severity])
        seen_rules: set[str] = set()
        for result in ordered:
            if result.severity is Severity.INFO or result.rule_id in seen_rules:
                continue
            seen_rules.add(result.rule_id)
            items.append(
                TodoItem(
                    title=f"修复 {result.rule_id}：{result.message}",
                    rationale=result.hint or "该问题会导致题库规范检查不通过。",
                    acceptance=f"talentpro check 不再出现 {result.rule_id} 的该项提示。",
                )
            )

    for item in DEFAULT_TODOS:
        if len(items) >= minimum and limit is None:
            break
        if item not in items:
            items.append(item)
        if limit is not None and len(items) >= limit:
            break

    if limit is not None:
        return items[:limit]
    return items


def suggest_from_report(report: CheckReport, *, minimum: int = MINIMUM_TODOS) -> list[TodoItem]:
    """从 :class:`CheckReport` 推导待办列表。"""
    return suggest_todos(report.results, minimum=minimum)


def validate_todos(items: Iterable[TodoItem], *, minimum: int = MINIMUM_TODOS) -> list[str]:
    """校验待办清单：数量下限、字段不重复、可验收。"""
    problems: list[str] = []
    collected = list(items)
    if len(collected) < minimum:
        problems.append(f"后续工作仅 {len(collected)} 条，少于要求下限 {minimum} 条")
    titles = [item.title for item in collected]
    if len(set(titles)) != len(titles):
        problems.append("存在重复的待办标题")
    for item in collected:
        if not item.acceptance.strip():
            problems.append(f"待办缺少验收标准：{item.title}")
    return problems


def render_todos(items: Iterable[TodoItem]) -> str:
    """渲染为可直接粘贴到平台表单的 Markdown。"""
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        lines.append(f"### TODO {index} · {item.title}")
        lines.append(f"- 背景：{item.rationale}")
        lines.append(f"- 验收：{item.acceptance}")
    return "\n".join(lines) + "\n"
