"""元数据类规则：schema 版本、任务信息、时限、资源、网络开关。"""

from __future__ import annotations

import re

from ..models import RuleResult, Severity
from ..spec import TaskSpec
from .base import finding, rule

CATEGORY = "metadata"

#: 本工具链支持的 task.toml schema 版本（对应 Harbor v0.5.0）。
SUPPORTED_SCHEMA_VERSION = "1.0"

NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
TAG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

VALID_DIFFICULTIES = ("easy", "medium", "hard")

#: 判卷脚本里出现这些命令，说明需要联网下载依赖。
NETWORK_COMMANDS = ("curl", "wget", "apt-get", "apk add", "pip install", "npm install", "uvx", "uv pip")

MIN_TIMEOUT_SEC = 60.0
MIN_MEMORY_MB = 512
MIN_STORAGE_MB = 1024


@rule("metadata.schema_version", "task.toml schema 版本", CATEGORY)
def check_schema_version(task: TaskSpec) -> list[RuleResult]:
    if not task.has_config:
        return []
    if task.version != SUPPORTED_SCHEMA_VERSION:
        return [
            finding(
                "metadata.schema_version",
                Severity.ERROR,
                f"task.toml 的 version 为 {task.version or '(缺失)'!r}，期望 {SUPPORTED_SCHEMA_VERSION!r}",
                "Harbor v0.5.0 只接受 version = \"1.0\"",
            )
        ]
    return []


@rule("metadata.task_info", "任务名称与描述", CATEGORY)
def check_task_info(task: TaskSpec) -> list[RuleResult]:
    if not task.has_config:
        return []
    results: list[RuleResult] = []
    name = task.name
    if not NAME_PATTERN.match(name):
        results.append(
            finding(
                "metadata.task_info",
                Severity.WARNING,
                f"task.name={name!r} 不符合 <org>/<task-name> 形式",
                "统一命名便于平台按题库维度聚合",
            )
        )
    if len(task.description.strip()) < 10:
        results.append(
            finding(
                "metadata.task_info",
                Severity.WARNING,
                "task.description 过短或缺失",
                "描述会展示在题目列表，建议一句话说明任务产出",
            )
        )
    if not task.author_name:
        results.append(
            finding(
                "metadata.task_info",
                Severity.WARNING,
                "metadata.author_name 缺失",
                "平台按作者维度统计出题量",
            )
        )
    return results


@rule("metadata.difficulty", "难度与标签", CATEGORY)
def check_difficulty(task: TaskSpec) -> list[RuleResult]:
    if not task.has_config:
        return []
    results: list[RuleResult] = []
    if task.difficulty not in VALID_DIFFICULTIES:
        results.append(
            finding(
                "metadata.difficulty",
                Severity.WARNING,
                f"metadata.difficulty={task.difficulty or '(缺失)'!r} 不在 {VALID_DIFFICULTIES}",
                "难度决定考生的时间预算",
            )
        )
    if not task.tags:
        results.append(
            finding("metadata.difficulty", Severity.INFO, "metadata.tags 为空", "标签用于题目检索与统计")
        )
    invalid_tags = [tag for tag in task.tags if not TAG_PATTERN.match(tag)]
    if invalid_tags:
        results.append(
            finding(
                "metadata.difficulty",
                Severity.WARNING,
                f"标签格式不规范：{', '.join(invalid_tags)}",
                "标签使用小写字母与连字符，例如 log-analysis",
            )
        )
    return results


@rule("metadata.timeouts", "超时配置", CATEGORY)
def check_timeouts(task: TaskSpec) -> list[RuleResult]:
    if not task.has_config:
        return []
    results: list[RuleResult] = []
    for section in ("verifier", "agent"):
        value = task.get(section, "timeout_sec")
        if not isinstance(value, (int, float)):
            results.append(
                finding(
                    "metadata.timeouts",
                    Severity.WARNING,
                    f"[{section}] 未配置 timeout_sec",
                    "缺少超时会让异常任务长时间占用算力",
                )
            )
            continue
        if value <= 0:
            results.append(
                finding("metadata.timeouts", Severity.ERROR, f"[{section}] timeout_sec 必须为正数，当前为 {value}")
            )
        elif value < MIN_TIMEOUT_SEC:
            results.append(
                finding(
                    "metadata.timeouts",
                    Severity.WARNING,
                    f"[{section}] timeout_sec={value} 小于 {MIN_TIMEOUT_SEC:g}s",
                    "判卷阶段需要安装依赖，建议至少 600s",
                )
            )
    return results


@rule("metadata.resources", "资源规格", CATEGORY)
def check_resources(task: TaskSpec) -> list[RuleResult]:
    if not task.has_config:
        return []
    results: list[RuleResult] = []
    checks = (
        ("cpus", 1, "个 CPU"),
        ("memory_mb", MIN_MEMORY_MB, "MB 内存"),
        ("storage_mb", MIN_STORAGE_MB, "MB 存储"),
    )
    for key, minimum, unit in checks:
        value = task.get("environment", key)
        if value is None:
            results.append(
                finding("metadata.resources", Severity.WARNING, f"[environment] 未配置 {key}", f"建议至少 {minimum} {unit}")
            )
        elif isinstance(value, (int, float)) and value < minimum:
            results.append(
                finding(
                    "metadata.resources",
                    Severity.WARNING,
                    f"[environment] {key}={value} 低于建议下限 {minimum} {unit}",
                )
            )
    return results


@rule("metadata.internet", "网络开关与判卷脚本匹配", CATEGORY)
def check_internet(task: TaskSpec) -> list[RuleResult]:
    if not task.has_config:
        return []
    verifier = task.verifier_source.lower()
    needs_network = any(command in verifier for command in NETWORK_COMMANDS)
    if needs_network and not task.allow_internet:
        return [
            finding(
                "metadata.internet",
                Severity.ERROR,
                "判卷脚本需要联网安装依赖，但 environment.allow_internet 为 false",
                "把 allow_internet 设为 true，或改为镜像内预装依赖",
            )
        ]
    if not needs_network and task.allow_internet:
        return [
            finding(
                "metadata.internet",
                Severity.INFO,
                "判卷脚本不需要联网，但 allow_internet 为 true",
                "关闭网络可以提升判卷环境的安全性与稳定性",
            )
        ]
    return []
