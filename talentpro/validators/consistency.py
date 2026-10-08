"""一致性规则：题面、判卷脚本、参考解与镜像之间的路径与产物必须对齐。"""

from __future__ import annotations

import re

from ..models import RuleResult, Severity
from ..spec import TaskSpec, extract_absolute_paths
from .base import finding, rule

CATEGORY = "consistency"

COPY_PATTERN = re.compile(r"^\s*COPY\s+(?P<source>\S+)\s+(?P<target>\S+)", re.MULTILINE | re.IGNORECASE)


def path_covered(path: str, text: str) -> bool:
    """判断文本是否「产出/读取」了某个路径。

    既要能识别字面量 ``/output/report.txt``，也要能识别拼接写法
    （``OUT_DIR="/output"`` + ``OUT="${OUT_DIR}/report.txt"``）。
    """
    if not path:
        return False
    if path in text:
        return True
    directory, _, name = path.rpartition("/")
    return bool(directory) and directory in text and bool(name) and name in text


@rule("consistency.output_paths", "产物路径贯穿题面与判卷", CATEGORY)
def check_output_paths(task: TaskSpec) -> list[RuleResult]:
    declared = task.declared_output_paths()
    if not declared:
        return []

    verifier = task.verifier_source
    results: list[RuleResult] = []
    for path in sorted(declared):
        if not path_covered(path, verifier):
            results.append(
                finding(
                    "consistency.output_paths",
                    Severity.ERROR,
                    f"题面声明了 {path}，但判卷脚本从未读取该路径",
                    "考生按题面交付却拿不到分数，说明题面与断言不一致",
                )
            )
    return results


@rule("consistency.input_paths", "输入路径可追溯", CATEGORY)
def check_input_paths(task: TaskSpec) -> list[RuleResult]:
    inputs = task.instruction_input_paths()
    if not inputs:
        return []

    haystack = "\n".join(filter(None, [task.dockerfile, task.verifier_source, task.solve_sh]))
    results: list[RuleResult] = []
    for path in sorted(inputs):
        if not path_covered(path, haystack):
            results.append(
                finding(
                    "consistency.input_paths",
                    Severity.WARNING,
                    f"题面提到输入 {path}，但镜像、参考解与判卷脚本均未出现",
                    "确认该文件确实由镜像提供，避免考生在容器内找不到输入",
                )
            )
    return results


@rule("consistency.solution_outputs", "参考解产出与断言一致", CATEGORY)
def check_solution_outputs(task: TaskSpec) -> list[RuleResult]:
    if task.solve_sh is None:
        return []
    declared = task.declared_output_paths()
    results: list[RuleResult] = []
    for path in sorted(declared):
        if not path_covered(path, task.solve_sh):
            results.append(
                finding(
                    "consistency.solution_outputs",
                    Severity.ERROR,
                    f"参考解 solve.sh 未写入 {path}",
                    "oracle 测试会因此失败，说明参考解与题面不一致",
                )
            )
    return results


@rule("consistency.dockerfile_sources", "镜像 COPY 源文件存在", CATEGORY)
def check_dockerfile_sources(task: TaskSpec) -> list[RuleResult]:
    if not task.dockerfile:
        return []
    results: list[RuleResult] = []
    environment_dir = task.root / "environment"
    for match in COPY_PATTERN.finditer(task.dockerfile):
        sources = [item for item in match.group("source").split() if not item.startswith("--")]
        for source in sources:
            if source.startswith("$") or "*" in source:
                continue
            if not (environment_dir / source).exists():
                results.append(
                    finding(
                        "consistency.dockerfile_sources",
                        Severity.ERROR,
                        f"Dockerfile 中 COPY {source} 在 environment/ 下不存在",
                        "构建上下文是 environment/ 目录，源文件缺失会导致镜像构建失败",
                    )
                )
    return results


@rule("consistency.env_dirs", "产出目录已预建", CATEGORY)
def check_env_dirs(task: TaskSpec) -> list[RuleResult]:
    if not task.dockerfile or not task.instruction:
        return []
    parent_dirs = {path.rsplit("/", 1)[0] for path in task.declared_output_paths() if "/" in path}
    results: list[RuleResult] = []
    for directory in sorted(parent_dirs):
        if directory not in task.dockerfile:
            results.append(
                finding(
                    "consistency.env_dirs",
                    Severity.INFO,
                    f"镜像未显式预建产出目录 {directory}",
                    "题面已要求脚本自行创建目录，此提示仅供确认",
                )
            )
    return results


@rule("consistency.absolute_paths", "无本机绝对路径", CATEGORY)
def check_absolute_paths(task: TaskSpec) -> list[RuleResult]:
    """题目内的绝对路径只能是容器内路径（/data、/output 等）。"""
    forbidden_prefixes = ("/Users/", "/home/", "/private/", "/var/folders/")
    results: list[RuleResult] = []
    for relative, source in task.all_sources.items():
        if source is None:
            continue
        for path in sorted(extract_absolute_paths(source)):
            if path.startswith(forbidden_prefixes):
                results.append(
                    finding(
                        "consistency.absolute_paths",
                        Severity.ERROR,
                        f"{relative} 出现本机绝对路径：{path}",
                        "容器内不存在该路径，改成 /data、/output 之类的容器路径",
                    )
                )
    return results
