"""产物契约规则：题面声明的报告格式必须可解析，且与判卷断言一致。"""

from __future__ import annotations

from ..models import RuleResult, Severity
from ..report import SECTION_PATTERN, parse_report
from ..spec import TaskSpec, fenced_blocks
from .base import finding, rule

CATEGORY = "report"


def section_titles(text: str) -> list[str]:
    """抽取文本中形如 ``=== X ===`` 的区块标题。"""
    titles: list[str] = []
    for raw in text.splitlines():
        match = SECTION_PATTERN.match(raw.strip())
        if match is not None:
            title = match.group("title")
            if title not in titles:
                titles.append(title)
    return titles


def example_block(task: TaskSpec) -> str | None:
    """题面里第一个包含区块标题的代码块，视为「标准输出样例」。"""
    for block in fenced_blocks(task.instruction):
        if "===" in block:
            return block
    return None


@rule("report.example_parsable", "输出样例可解析", CATEGORY)
def check_example_parsable(task: TaskSpec) -> list[RuleResult]:
    block = example_block(task)
    if block is None:
        return []
    sections = parse_report(block)
    if not sections:
        return [
            finding(
                "report.example_parsable",
                Severity.ERROR,
                "题面给出的输出样例无法按 === 区块 === 规则解析",
                "样例必须能被判卷脚本解析，否则考生会照着错误格式实现",
            )
        ]
    empty = [title for title, lines in sections.items() if not lines]
    if empty:
        return [
            finding(
                "report.example_parsable",
                Severity.WARNING,
                f"输出样例中的区块为空：{', '.join(empty)}",
                "示例至少要有一行内容",
            )
        ]
    return []


@rule("report.sections_aligned", "区块标题与判卷一致", CATEGORY)
def check_sections_aligned(task: TaskSpec) -> list[RuleResult]:
    declared = section_titles(task.instruction)
    if not declared:
        return []

    verifier = task.verifier_source
    missing_in_verifier = [title for title in declared if title not in verifier]
    results: list[RuleResult] = []
    if missing_in_verifier:
        results.append(
            finding(
                "report.sections_aligned",
                Severity.ERROR,
                f"题面声明但判卷未校验的区块：{', '.join(missing_in_verifier)}",
                "要么补断言，要么从题面移除，避免出现无人校验的产出",
            )
        )

    checked_only = [
        title for title in section_titles(verifier) if title not in declared and title not in missing_in_verifier
    ]
    if checked_only:
        results.append(
            finding(
                "report.sections_aligned",
                Severity.WARNING,
                f"判卷校验但题面未声明的区块：{', '.join(checked_only)}",
                "考生看不到该要求，容易失分",
            )
        )
    return results
