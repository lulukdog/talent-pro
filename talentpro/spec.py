"""题目目录的解析与数据模型。

一个 Harbor 题目目录的标准结构::

    exam_001/
    ├── task.toml
    ├── instruction.md
    ├── environment/Dockerfile
    ├── solution/solve.sh
    └── tests/test.sh

``load_task`` 采取「尽力解析」策略：文件缺失不抛错，交由
``talentpro.validators`` 输出可读的检查结论。
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TASK_CONFIG_FILE = "task.toml"
INSTRUCTION_FILE = "instruction.md"
DOCKERFILE = "environment/Dockerfile"
SOLVE_SCRIPT = "solution/solve.sh"
VERIFIER_SCRIPT = "tests/test.sh"

#: 需要做敏感信息扫描的文本文件后缀。
SCANNABLE_SUFFIXES = frozenset(
    {".py", ".sh", ".md", ".txt", ".toml", ".yaml", ".yml", ".json", ".cfg", ".ini", ".log", ".cff"}
)

SCANNABLE_NAMES = frozenset({"Dockerfile", "Makefile", "LICENSE"})

SKIP_DIRS = frozenset({".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"})

#: 单个文件参与扫描的大小上限（字节）。
MAX_SCAN_BYTES = 512 * 1024

#: 绝对路径，例如 ``/output/report.txt``。避开 URL（前一个字符是 ``:`` 或 ``/``）。
ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![\w:/])/(?:[\w.-]+)(?:/[\w.-]+)+")

#: 容器内的常见目录，用于把「容器路径」与 HTTP 路由（``/api/users``）区分开。
CONTAINER_ROOTS = frozenset(
    {"data", "output", "logs", "tests", "app", "opt", "srv", "workspace", "root", "etc", "tmp", "usr", "var", "mnt"}
)

FENCE_PATTERN = re.compile(r"```[^\n]*\n(?P<body>.*?)```", re.DOTALL)


class TaskFormatError(Exception):
    """题目目录无法解析（例如缺少 ``task.toml`` 或 TOML 非法）。"""


@dataclass
class TaskSpec:
    """解析后的题目描述，供各校验规则消费。"""

    root: Path
    config: dict[str, Any]
    instruction: str
    dockerfile: str | None
    solve_sh: str | None
    test_sh: str | None
    test_sources: dict[str, str]
    environment_files: tuple[str, ...]

    # --- 元信息 ---------------------------------------------------------
    def get(self, *keys: str, default: Any = None) -> Any:
        """按层级读取 ``task.toml`` 字段，例如 ``get("task", "name")``。"""
        node: Any = self.config
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    @property
    def version(self) -> str:
        value = self.config.get("version")
        return value if isinstance(value, str) else ""

    @property
    def name(self) -> str:
        name = self.get("task", "name")
        return name if isinstance(name, str) else self.root.name

    @property
    def slug(self) -> str:
        return self.name.split("/")[-1]

    @property
    def description(self) -> str:
        value = self.get("task", "description")
        return value if isinstance(value, str) else ""

    @property
    def author_name(self) -> str:
        value = self.get("metadata", "author_name")
        return value if isinstance(value, str) else ""

    @property
    def difficulty(self) -> str:
        value = self.get("metadata", "difficulty")
        return value if isinstance(value, str) else ""

    @property
    def category(self) -> str:
        value = self.get("metadata", "category")
        return value if isinstance(value, str) else ""

    @property
    def tags(self) -> tuple[str, ...]:
        value = self.get("metadata", "tags", default=[])
        if isinstance(value, list):
            return tuple(str(item) for item in value)
        return ()

    @property
    def allow_internet(self) -> bool:
        return bool(self.get("environment", "allow_internet", default=False))

    @property
    def has_config(self) -> bool:
        return bool(self.config)

    # --- 源码聚合 -------------------------------------------------------
    @property
    def verifier_source(self) -> str:
        """判卷相关源码（``test.sh`` + 全部 ``tests/*.py``）。"""
        return "\n".join([self.test_sh or "", *self.test_sources.values()])

    @property
    def all_sources(self) -> dict[str, str]:
        """相对路径 → 文本，用于扫描与一致性比对。"""
        sources: dict[str, str] = {INSTRUCTION_FILE: self.instruction}
        if self.dockerfile is not None:
            sources[DOCKERFILE] = self.dockerfile
        if self.solve_sh is not None:
            sources[SOLVE_SCRIPT] = self.solve_sh
        if self.test_sh is not None:
            sources[VERIFIER_SCRIPT] = self.test_sh
        for name, source in self.test_sources.items():
            sources[f"tests/{name}"] = source
        return sources

    # --- 路径抽取 -------------------------------------------------------
    def declared_output_paths(self) -> set[str]:
        """题面中声明的输出路径（``/output`` 下）。"""
        return {p for p in extract_absolute_paths(self.instruction) if p.startswith("/output")}

    def instruction_input_paths(self) -> set[str]:
        """题面中声明的输入路径（容器路径，排除 ``/output``）。"""
        return {p for p in extract_container_paths(self.instruction) if not p.startswith("/output")}


def read_text(path: Path) -> str | None:
    """读取文本文件；不存在时返回 ``None``。"""
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def extract_absolute_paths(text: str) -> set[str]:
    """抽取文本中的绝对路径（去掉 URL 干扰）。"""
    return {match.group(0) for match in ABSOLUTE_PATH_PATTERN.finditer(text)}


def extract_container_paths(text: str) -> set[str]:
    """只保留容器内路径，避免把 HTTP 路由（``/api/users``）误判为文件路径。"""
    return {
        path
        for path in extract_absolute_paths(text)
        if path.split("/")[1:2] and path.split("/")[1] in CONTAINER_ROOTS
    }


def fenced_blocks(text: str) -> list[str]:
    """抽取 Markdown 围栏代码块的内容。"""
    return [match.group("body") for match in FENCE_PATTERN.finditer(text)]


def iter_text_files(root: Path) -> Iterator[tuple[str, str]]:
    """遍历目录下可扫描的文本文件，产出 ``(相对路径, 文本)``。"""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name not in SCANNABLE_NAMES and path.suffix.lower() not in SCANNABLE_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_BYTES:
                continue
            yield str(path.relative_to(root)), path.read_text(encoding="utf-8", errors="replace")
        except OSError:  # 权限/编码等偶发问题不应中断扫描
            continue


def load_task(root: str | Path) -> TaskSpec:
    """解析题目目录。

    Raises:
        TaskFormatError: 目录不存在、缺少 ``task.toml`` 或 TOML 无法解析。
    """
    task_root = Path(root).expanduser().resolve()
    if not task_root.is_dir():
        raise TaskFormatError(f"题目目录不存在：{task_root}")

    config_path = task_root / TASK_CONFIG_FILE
    if not config_path.is_file():
        raise TaskFormatError(f"缺少任务配置文件：{TASK_CONFIG_FILE}")

    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as exc:
        raise TaskFormatError(f"{TASK_CONFIG_FILE} 解析失败：{exc}") from exc

    tests_dir = task_root / "tests"
    test_sources: dict[str, str] = {}
    if tests_dir.is_dir():
        for path in sorted(tests_dir.glob("*.py")):
            test_sources[path.name] = read_text(path) or ""

    environment_dir = task_root / "environment"
    environment_files: tuple[str, ...] = ()
    if environment_dir.is_dir():
        environment_files = tuple(
            sorted(p.name for p in environment_dir.iterdir() if p.is_file() and p.name != "Dockerfile")
        )

    return TaskSpec(
        root=task_root,
        config=config,
        instruction=read_text(task_root / INSTRUCTION_FILE) or "",
        dockerfile=read_text(task_root / DOCKERFILE),
        solve_sh=read_text(task_root / SOLVE_SCRIPT),
        test_sh=read_text(task_root / VERIFIER_SCRIPT),
        test_sources=test_sources,
        environment_files=environment_files,
    )
