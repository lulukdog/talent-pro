"""题面类规则：结构完整、输出路径可定位、格式样例可解析、不泄露判卷细节。"""

from __future__ import annotations

from ..models import RuleResult, Severity
from ..spec import TaskSpec, fenced_blocks
from .base import finding, rule

CATEGORY = "instruction"

#: 题面必须覆盖的语义区块（中英文任选其一）。
REQUIRED_SECTIONS: dict[str, tuple[str, ...]] = {
    "输入": ("输入", "input"),
    "要求": ("要求", "任务", "requirement", "task"),
    "输出格式": ("输出", "output", "格式", "format"),
    "提交": ("提交", "submission", "deliverable"),
}

MIN_CHARS = 200
MAX_CHARS = 12000

#: 出现在题面里会泄露判卷实现的词。
LEAK_HINTS = ("test_state", "pytest", "reward.txt", "/tests/", "ctrf")


@rule("instruction.sections", "题面语义区块", CATEGORY)
def check_sections(task: TaskSpec) -> list[RuleResult]:
    if not task.instruction:
        return [
            finding("instruction.sections", Severity.ERROR, "题面为空", "instruction.md 是考生看到的唯一描述")
        ]
    lowered = task.instruction.lower()
    missing = [
        name
        for name, keywords in REQUIRED_SECTIONS.items()
        if not any(keyword.lower() in lowered for keyword in keywords)
    ]
    if len(missing) >= 2:
        return [
            finding(
                "instruction.sections",
                Severity.ERROR,
                f"题面缺少关键区块：{', '.join(missing)}",
                "按「输入 / 要求 / 输出格式 / 提交」组织题面，考生才能稳定复现",
            )
        ]
    if missing:
        return [
            finding(
                "instruction.sections",
                Severity.WARNING,
                f"题面可能缺少区块：{', '.join(missing)}",
                "补齐后可以减少考生提问",
            )
        ]
    return []


@rule("instruction.output_path", "输出路径声明", CATEGORY)
def check_output_path(task: TaskSpec) -> list[RuleResult]:
    if not task.instruction:
        return []
    if not task.declared_output_paths():
        return [
            finding(
                "instruction.output_path",
                Severity.ERROR,
                "题面没有声明任何 /output 下的产物路径",
                "判卷脚本按固定路径读取产物，题面必须写明",
            )
        ]
    return []


@rule("instruction.format_example", "输出格式样例", CATEGORY)
def check_format_example(task: TaskSpec) -> list[RuleResult]:
    if not task.instruction:
        return []
    if not fenced_blocks(task.instruction):
        return [
            finding(
                "instruction.format_example",
                Severity.WARNING,
                "题面没有代码块形式的输出样例",
                "给出可复制的样例可以显著降低格式类失败率",
            )
        ]
    return []


@rule("instruction.no_test_leak", "题面不泄露判卷细节", CATEGORY)
def check_no_leak(task: TaskSpec) -> list[RuleResult]:
    if not task.instruction:
        return []
    hits = [hint for hint in LEAK_HINTS if hint in task.instruction]
    if hits:
        return [
            finding(
                "instruction.no_test_leak",
                Severity.WARNING,
                f"题面出现了判卷实现相关字样：{', '.join(hits)}",
                "只描述「做完是什么样」，不要暴露断言的实现方式",
            )
        ]
    return []


@rule("instruction.length", "题面长度", CATEGORY)
def check_length(task: TaskSpec) -> list[RuleResult]:
    size = len(task.instruction.strip())
    if not task.instruction:
        return []
    if size < MIN_CHARS:
        return [
            finding(
                "instruction.length",
                Severity.WARNING,
                f"题面仅 {size} 字，可能缺少约束条件",
                f"建议不少于 {MIN_CHARS} 字，把边界条件写清楚",
            )
        ]
    if size > MAX_CHARS:
        return [
            finding(
                "instruction.length",
                Severity.INFO,
                f"题面 {size} 字，偏长",
                "过长的题面容易让考生漏读关键约束",
            )
        ]
    return []
