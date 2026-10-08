"""结构类规则：必填文件、文件非空、命名一致、canary 声明、输入数据。"""

from __future__ import annotations

from ..models import RuleResult, Severity
from ..spec import (
    DOCKERFILE,
    INSTRUCTION_FILE,
    SOLVE_SCRIPT,
    TASK_CONFIG_FILE,
    VERIFIER_SCRIPT,
    TaskSpec,
)
from .base import finding, rule

CATEGORY = "structure"

REQUIRED_FILES: dict[str, str] = {
    TASK_CONFIG_FILE: "任务配置",
    INSTRUCTION_FILE: "题面",
    DOCKERFILE: "环境镜像定义",
    VERIFIER_SCRIPT: "判卷入口",
}

OPTIONAL_FILES: dict[str, str] = {
    SOLVE_SCRIPT: "参考解（Oracle 测试必需）",
}

CANARY_MARKER = "terminal-bench-canary"


@rule("structure.required_files", "必填文件完整性", CATEGORY)
def check_required_files(task: TaskSpec) -> list[RuleResult]:
    results: list[RuleResult] = []
    for relative, description in REQUIRED_FILES.items():
        if not (task.root / relative).is_file():
            results.append(
                finding(
                    "structure.required_files",
                    Severity.ERROR,
                    f"缺少{description}：{relative}",
                    "Harbor 任务的必填文件，缺失会导致上传后无法判卷",
                )
            )
    for relative, description in OPTIONAL_FILES.items():
        if not (task.root / relative).is_file():
            results.append(
                finding(
                    "structure.required_files",
                    Severity.WARNING,
                    f"缺少{description}：{relative}",
                    "没有参考解将无法运行 oracle 自测",
                )
            )
    if not task.test_sources:
        results.append(
            finding(
                "structure.required_files",
                Severity.WARNING,
                "tests/ 下没有 Python 断言模块",
                "建议提供 tests/test_state.py 之类的断言，便于定位失败原因",
            )
        )
    return results


@rule("structure.empty_files", "文件内容非空", CATEGORY)
def check_empty_files(task: TaskSpec) -> list[RuleResult]:
    results: list[RuleResult] = []
    for relative, source in task.all_sources.items():
        if source is not None and not source.strip():
            results.append(
                finding(
                    "structure.empty_files",
                    Severity.ERROR,
                    f"文件为空：{relative}",
                    "空文件会被判卷流程直接判失败",
                )
            )
    return results


@rule("structure.task_naming", "目录名与任务名一致", CATEGORY)
def check_task_naming(task: TaskSpec) -> list[RuleResult]:
    if not task.has_config:
        return []
    normalized = task.slug.replace("-", "_").lower()
    if task.root.name.replace("-", "_").lower() != normalized:
        return [
            finding(
                "structure.task_naming",
                Severity.WARNING,
                f"目录名 {task.root.name!r} 与任务名 {task.slug!r} 不一致",
                "平台按目录名归档，命名不一致会增加人工核对成本",
            )
        ]
    return []


@rule("structure.canary", "canary 声明", CATEGORY)
def check_canary(task: TaskSpec) -> list[RuleResult]:
    if task.solve_sh is None:
        return []
    if CANARY_MARKER not in task.solve_sh:
        return [
            finding(
                "structure.canary",
                Severity.WARNING,
                "solution/solve.sh 缺少 Terminal-Bench canary 声明",
                "题库数据需保留 canary 注释，避免被语料收录",
            )
        ]
    return []


@rule("structure.environment_data", "题目输入数据", CATEGORY)
def check_environment_data(task: TaskSpec) -> list[RuleResult]:
    if task.dockerfile is None:
        return []
    if not task.environment_files:
        return [
            finding(
                "structure.environment_data",
                Severity.WARNING,
                "environment/ 下除 Dockerfile 外没有输入数据文件",
                "自包含题目建议把输入数据随镜像分发，而不是运行时下载",
            )
        ]
    return []
